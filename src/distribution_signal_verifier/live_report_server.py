"""Serve the signal report as a live, browser-openable web page.

The page is rendered on every request. Oracle credentials are loaded only on
the server from a private Python configuration module, and the RMU mapping,
signal list, and channel protocol are read again whenever the user opens or
refreshes the page. JSON files remain available as a safe offline fallback.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html as html_lib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from distribution_signal_verifier.report_store import ReportStore

from distribution_signal_verifier.distribution_signal_verifier import (
    DEFAULT_TEMPLATE,
    InputError,
    RmuMapping,
    build_payload,
    build_distribution_point_sql,
    build_distribution_protocol_sql,
    build_rmu_search_sql,
    build_smart_inventory_sql,
    assert_oracle_read_only_sql,
    load_json_rows,
    normalize_mapping,
    normalize_signals,
    query_rmu_mapping,
    _mapping_selector,
    render_report_text,
)


LOGGER = logging.getLogger("distribution_signal_verifier.server")


@dataclass(frozen=True)
class LiveConfig:
    template: Path
    host: str
    port: int
    main_signals_json: Path | None
    distribution_signals_json: Path | None
    mapping_json: Path | None
    main_signal_sql: Path | None
    distribution_signal_sql: Path | None
    refresh_seconds: int
    mapping_sql: Path | None = None
    distribution_point_sql: Path | None = None
    distribution_protocol_sql: Path | None = None


@dataclass
class OracleSettings:
    host: str = ""
    port: str = "1521"
    service: str = ""
    dsn: str = ""
    username: str = ""
    password: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password and (self.dsn or (self.host and self.service)))

    @property
    def display(self) -> dict[str, Any]:
        # Health responses intentionally expose only whether the server has a
        # usable private connection. Never return host, DSN, username, or any
        # other database detail to browser users.
        return {"configured": self.configured}


@lru_cache(maxsize=1)
def _load_local_config() -> dict[str, Any]:
    """Load the private JSON configuration beside the source or packaged EXE."""

    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "config"
    for filename in ("配网报告配置.json", "report_config.json"):
        config_path = root / filename
        if not config_path.exists():
            continue
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InputError(f"配置文件无法读取或格式错误：{config_path}") from exc
        if not isinstance(data, dict):
            raise InputError(f"配置文件顶层必须是 JSON 对象：{config_path}")
        return data
    return {}


def _private_oracle_value(name: str, environment_name: str, default: str = "") -> str:
    """Read Oracle settings from the canonical report_config.json only."""

    json_names = {
        "ORACLE_HOST": "host",
        "ORACLE_PORT": "port",
        "ORACLE_SERVICE": "service",
        "ORACLE_DSN": "dsn",
        "ORACLE_USER": "user",
        "ORACLE_PASSWORD": "password",
    }
    oracle_config = _load_local_config().get("oracle", {})
    if not isinstance(oracle_config, dict):
        return str(default or "")
    value = oracle_config.get(json_names.get(name, name), default)
    return str(value if value not in (None, "") else (default or ""))


def _read_template_payload(template: str) -> dict[str, Any]:
    match = re.search(
        r'<script\s+id="payload"\s+type="application/json">(.*?)</script>',
        template,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        raise InputError("模板中没有找到 payload JSON")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise InputError(f"模板 payload JSON 无效：{exc}") from exc
    if not isinstance(data, dict):
        raise InputError("模板 payload 必须是 JSON 对象")
    return data


def _split_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,;\n]+", value) if item.strip()]


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _application_root() -> Path:
    """Directory that owns config/data/logs for source and packaged execution."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _application_version() -> str:
    version_path = _application_root() / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def _find_print_browser() -> Path | None:
    """Find a local Edge/Chrome/Chromium binary for server-side PDF archiving."""
    names = ["msedge", "msedge.exe", "chrome", "chrome.exe", "chromium", "chromium.exe", "chromium-browser"]
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved)
    env = os.environ
    roots = [env.get("PROGRAMFILES"), env.get("PROGRAMFILES(X86)"), env.get("LOCALAPPDATA")]
    candidates: list[Path] = []
    for raw in roots:
        if not raw:
            continue
        root = Path(raw)
        candidates.extend([
            root / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            root / "Google" / "Chrome" / "Application" / "chrome.exe",
        ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _html_add_root_class(html_text: str, class_name: str) -> str:
    """Add a CSS class to the root <html> tag without reserializing the document."""
    match = re.search(r"<html\b[^>]*>", html_text, flags=re.IGNORECASE)
    if not match:
        return html_text
    tag = match.group(0)
    class_match = re.search(r"\bclass\s*=\s*([\"'])(.*?)\1", tag, flags=re.IGNORECASE | re.DOTALL)
    if class_match:
        classes = class_match.group(2).split()
        if class_name not in classes:
            classes.append(class_name)
        quote = class_match.group(1)
        new_attr = f"class={quote}{' '.join(classes)}{quote}"
        new_tag = tag[:class_match.start()] + new_attr + tag[class_match.end():]
    else:
        new_tag = tag[:-1] + f' class="{class_name}">'
    return html_text[:match.start()] + new_tag + html_text[match.end():]


def _render_pdf_with_browser(html_path: Path, pdf_path: Path) -> bool:
    browser = _find_print_browser()
    if browser is None:
        LOGGER.warning("server PDF archive skipped: no Edge/Chrome/Chromium binary found")
        return False
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    file_url = html_path.resolve().as_uri()
    with tempfile.TemporaryDirectory(prefix="ete-pdf-") as profile:
        base = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--run-all-compositor-stages-before-draw",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf_path.resolve()}",
            file_url,
        ]
        try:
            result = subprocess.run(base, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45, check=False)
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is None or result.returncode != 0 or not pdf_path.exists():
            # Compatibility fallback for older browser builds.
            fallback = [item for item in base if item != "--headless=new"]
            fallback.insert(1, "--headless")
            try:
                subprocess.run(fallback, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45, check=False)
            except (OSError, subprocess.TimeoutExpired):
                return False
    return pdf_path.is_file() and pdf_path.stat().st_size > 0


class LiveDataProvider:
    def __init__(self, config: LiveConfig):
        self.config = config
        self.template = config.template.read_text(encoding="utf-8")
        self.template_payload = _read_template_payload(self.template)
        self.oracle = OracleSettings(
            host=_private_oracle_value("ORACLE_HOST", "ORACLE_HOST"),
            port=_private_oracle_value("ORACLE_PORT", "ORACLE_PORT", "1521") or "1521",
            service=_private_oracle_value("ORACLE_SERVICE", "ORACLE_SERVICE"),
            dsn=_private_oracle_value("ORACLE_DSN", "ORACLE_DSN"),
            username=_private_oracle_value("ORACLE_USER", "ORACLE_USER"),
            password=_private_oracle_value("ORACLE_PASSWORD", "ORACLE_PASSWORD"),
        )
        security_config = _load_local_config().get("security", {})
        configured_print_password = "NARI"
        if isinstance(security_config, dict):
            configured_print_password = str(security_config.get("print_password") or "NARI")
        self.print_password_hash = (
            hashlib.sha256(configured_print_password.encode("utf-8")).hexdigest()
            if configured_print_password
            else ""
        )
        self.report_store = ReportStore(_application_root())
        history_path = config.template.parent / "history.html"
        self.history_template = history_path.read_text(encoding="utf-8") if history_path.is_file() else ""
        dashboard_path = config.template.parent / "dashboard.html"
        self.dashboard_template = dashboard_path.read_text(encoding="utf-8") if dashboard_path.is_file() else ""

    def archive_report(self, data: Mapping[str, Any], client_ip: str = "") -> dict[str, Any]:
        is_draft = bool(data.get("is_draft"))
        return self.report_store.save_report(
            data,
            client_ip=client_ip,
            software_version=_application_version(),
            pdf_renderer=None if is_draft else _render_pdf_with_browser,
        )

    def generate_report_pdf(self, report_uuid: str) -> dict[str, Any]:
        """Generate/re-generate a PDF snapshot without changing draft/final status."""
        report = self.report_store.get_report(report_uuid)
        if report is None:
            raise ValueError("report not found")
        html_path = self.report_store.resolve_report_file(report_uuid, "html")
        if html_path is None:
            raise ValueError("archived HTML snapshot not found")
        if _find_print_browser() is None:
            raise ValueError("无法生成 PDF：服务端未找到 Edge / Chrome / Chromium。")

        report_dir = html_path.parent
        pdf_path = report_dir / "report.pdf"
        staging_pdf = report_dir / "report.generating.pdf"
        staging_html = report_dir / "report.generating.html"
        source_html = html_path
        is_draft = bool(int(report.get("is_draft") or 0))
        try:
            staging_pdf.unlink(missing_ok=True)
            staging_html.unlink(missing_ok=True)
            if is_draft:
                html_text = html_path.read_text(encoding="utf-8")
                staging_html.write_text(
                    _html_add_root_class(html_text, "print-draft"),
                    encoding="utf-8",
                )
                source_html = staging_html
            if not _render_pdf_with_browser(source_html, staging_pdf):
                raise ValueError("PDF 生成失败，请检查服务端 Edge / Chrome / Chromium。")
            staging_pdf.replace(pdf_path)
            saved = self.report_store.register_report_pdf(report_uuid, pdf_path)
        finally:
            staging_pdf.unlink(missing_ok=True)
            staging_html.unlink(missing_ok=True)

        return {
            "report_uuid": report_uuid,
            "is_draft": bool(int(saved.get("is_draft") or 0)),
            "pdf_saved": True,
            "pdf_available": True,
        }

    @property
    def oracle_enabled(self) -> bool:
        return self.oracle.configured

    def _connection(self) -> Any:
        try:
            import oracledb  # type: ignore
        except ImportError as exc:
            raise InputError(f"Oracle 驱动加载失败：{exc}") from exc
        if not self.oracle.configured:
            raise InputError("服务端未配置 Oracle 连接信息，请检查 config/report_config.json（打包版检查 EXE 同目录 report_config.json）")
        dsn = self.oracle.dsn
        if not dsn:
            dsn = oracledb.makedsn(
                self.oracle.host,
                int(self.oracle.port),
                service_name=self.oracle.service,
            )
        return oracledb.connect(user=self.oracle.username, password=self.oracle.password, dsn=dsn)

    def mappings(self, rmu_names: Sequence[str]) -> list[RmuMapping]:
        if self.config.mapping_json:
            rows = load_json_rows(self.config.mapping_json)
            mappings = [normalize_mapping(row) for row in rows]
            if rmu_names:
                selectors = [str(name).strip() for name in rmu_names if str(name).strip()]
                wanted = set(selectors)
                mappings = [
                    item for item in mappings
                    if _mapping_selector(item) in wanted
                    or item.rmu_name in wanted
                    or (item.adms_gss_fid and f"fid:{item.adms_gss_fid}" in wanted)
                ]
                order = {selector: index for index, selector in enumerate(selectors)}
                mappings.sort(key=lambda item: min(
                    order.get(_mapping_selector(item), 10**9),
                    order.get(item.rmu_name, 10**9),
                    order.get(f"fid:{item.adms_gss_fid}", 10**9) if item.adms_gss_fid else 10**9,
                ))
            return mappings
        if self.config.mapping_sql:
            rows = self._sql_rows(self.config.mapping_sql, "rmu_name", rmu_names)
            return [normalize_mapping(row) for row in rows]
        if not rmu_names:
            return []
        if not self.oracle_enabled:
            return []
        connection = self._connection()
        try:
            return query_rmu_mapping(connection, rmu_names)
        finally:
            connection.close()

    def _sql_rows(
        self,
        sql_path: Path,
        bind_name: str,
        values: Sequence[Any],
    ) -> list[Mapping[str, Any]]:
        if not self.oracle_enabled:
            raise InputError("配置了信号 SQL，但没有配置 ORACLE_USER、ORACLE_PASSWORD、ORACLE_DSN")
        sql = sql_path.read_text(encoding="utf-8")
        assert_oracle_read_only_sql(sql)
        connection = self._connection()
        rows: list[Mapping[str, Any]] = []
        cursor = connection.cursor()
        try:
            for value in values:
                cursor.execute(sql, {bind_name: value})
                columns = [str(description[0]) for description in cursor.description]
                rows.extend(dict(zip(columns, row)) for row in cursor.fetchall())
        finally:
            cursor.close()
            connection.close()
        return rows

    def _execute_rows(self, sql: str, binds: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        if not self.oracle_enabled:
            raise InputError("实时查询需要先配置 ORACLE_USER、ORACLE_PASSWORD、ORACLE_DSN")
        assert_oracle_read_only_sql(sql)
        connection = self._connection()
        cursor = connection.cursor()
        try:
            cursor.execute(sql, dict(binds))
            columns = [str(description[0]) for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            cursor.close()
            connection.close()

    def signal_rows(
        self,
        network: str,
        rmu_names: Sequence[str],
        mappings: Sequence[RmuMapping],
    ) -> list[Mapping[str, Any]]:
        if network == "distribution" and self.config.distribution_point_sql:
            # Keep the supplied point SQL unchanged.  For a multi-RMU report,
            # execute the existing single-RMU query once per selected mapping
            # and attach the owning COMBINED_ID in the application layer.
            # Some site SQL returns only point fields (no COMBINED_ID column),
            # so a batched result cannot otherwise be split back into 3.x/4.x
            # device groups.
            tagged_rows: list[Mapping[str, Any]] = []
            for item in mappings:
                combined_id = item.combined_id
                if combined_id in (None, ""):
                    continue
                device_rows = self._sql_rows(
                    self.config.distribution_point_sql, "combined_id", [combined_id]
                )
                for row in device_rows:
                    tagged = dict(row)
                    if not any(
                        str(key).lower() in {"combined_id", "com_id"}
                        for key in tagged
                    ):
                        tagged["COMBINED_ID"] = combined_id
                    # Presentation ownership only.  The existing site SQL is
                    # executed unchanged once per selected RMU; stamp the RMU
                    # identity on its returned rows so the browser can render
                    # independent 3.x/4.x groups without relying on SQL output
                    # columns that the supplied query does not return.
                    tagged["RMU_NAME"] = item.rmu_name
                    tagged["RMU_DISPLAY_NAME"] = item.adms_gss_fid or item.rmu_name
                    tagged_rows.append(tagged)
            return tagged_rows
        sql_path = self.config.main_signal_sql if network == "main" else self.config.distribution_signal_sql
        json_path = self.config.main_signals_json if network == "main" else self.config.distribution_signals_json
        if sql_path:
            return self._sql_rows(sql_path, "rmu_name", rmu_names)
        if json_path:
            return load_json_rows(json_path)
        if network == "distribution" and mappings:
            ids = [item.combined_id for item in mappings if item.combined_id not in (None, "")]
            if not ids:
                return []
            sql, binds = build_distribution_point_sql(ids)
            return self._execute_rows(sql, binds)
        if network == "main":
            # Backward-compatible fallback: the original report remains
            # usable while the main-network point SQL is being connected.
            return list(self.template_payload.get("points", []))
        return []

    def protocol_mappings(self, mappings: Sequence[RmuMapping]) -> list[RmuMapping]:
        if not mappings:
            return list(mappings)
        if self.config.mapping_json or self.config.distribution_signals_json:
            return list(mappings)
        ids = [item.combined_id for item in mappings if item.combined_id not in (None, "")]
        if not ids:
            return list(mappings)
        if self.config.distribution_protocol_sql:
            rows = self._sql_rows(self.config.distribution_protocol_sql, "combined_id", ids)
        else:
            sql, binds = build_distribution_protocol_sql(ids)
            rows = self._execute_rows(sql, binds)
        channel_rows = [normalize_mapping(row) for row in rows]
        by_id = {str(item.combined_id): item for item in channel_rows}
        enriched: list[RmuMapping] = []
        for item in mappings:
            channel = by_id.get(str(item.combined_id))
            if channel is None:
                enriched.append(item)
                continue
            enriched.append(
                replace(
                    item,
                    ip=channel.ip or item.ip,
                    protocol_name=channel.protocol_name or item.protocol_name,
                )
            )
        return enriched

    def search_rmus(self, keyword: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return lightweight RMU candidates for the search selector."""
        if not keyword.strip():
            return []
        if self.config.mapping_json:
            rows = load_json_rows(self.config.mapping_json)
            mappings = [normalize_mapping(row) for row in rows]
            key = keyword.strip().lower()
            matches = [m for m in mappings if key in m.rmu_name.lower()]
        else:
            if not self.oracle_enabled:
                return []
            sql, binds = build_rmu_search_sql(keyword, limit)
            matches = [normalize_mapping(row) for row in self._execute_rows(sql, binds)]
        return [
            {
                "combined_id": "" if m.combined_id in (None, "") else str(m.combined_id),
                "rmu_name": m.rmu_name,
                "adms_gss_fid": m.adms_gss_fid,
                "rmu_type": m.rmu_type,
                "smart_type": m.smart_type,
                "nop": m.nop,
            }
            for m in matches[:limit]
        ]

    @staticmethod
    def _mapping_record(mapping: RmuMapping) -> dict[str, Any]:
        return {
            "combined_id": mapping.combined_id,
            "rmu_name": mapping.rmu_name,
            "display_name": mapping.adms_gss_fid or mapping.rmu_name,
            "adms_gss_fid": mapping.adms_gss_fid or mapping.rmu_name,
            "rmu_type": mapping.rmu_type,
            "smart_type": mapping.smart_type,
            "nop": mapping.nop,
            "function_location": mapping.function_location,
            "feeder_name": mapping.feeder_name,
            "substation_name": mapping.substation_name,
            "subcontrolarea_name": mapping.subcontrolarea_name,
        }

    @staticmethod
    def _matches_scope(mapping: RmuMapping, filters: Mapping[str, str]) -> bool:
        checks = (
            (mapping.subcontrolarea_name, str(filters.get("subcontrolarea") or "")),
            (mapping.substation_name, str(filters.get("substation") or "")),
            (mapping.feeder_name, str(filters.get("feeder") or "")),
        )
        return all(
            not needle.strip() or needle.strip().lower() in (value or "").lower()
            for value, needle in checks
        )

    def _dashboard_inventory(self, filters: Mapping[str, str]) -> tuple[list[dict[str, Any]], str, str, str]:
        """Return SMART inventory, source label, refresh time and optional warning."""
        warning = ""
        refreshed_at = ""
        if self.config.mapping_json:
            mappings = [normalize_mapping(row) for row in load_json_rows(self.config.mapping_json)]
            records = [
                self._mapping_record(item)
                for item in mappings
                if item.smart_type.upper() == "SMART" and self._matches_scope(item, filters)
            ]
            if records:
                refreshed_at = self.report_store.upsert_inventory(records)
            return records, "mapping-json", refreshed_at, warning

        if self.oracle_enabled:
            try:
                sql, binds = build_smart_inventory_sql(
                    str(filters.get("substation") or ""),
                    str(filters.get("feeder") or ""),
                    str(filters.get("subcontrolarea") or ""),
                )
                mappings = [normalize_mapping(row) for row in self._execute_rows(sql, binds)]
                records = [self._mapping_record(item) for item in mappings if item.smart_type.upper() == "SMART"]
                refreshed_at = self.report_store.upsert_inventory(records) if records else _now()
                return records, "oracle", refreshed_at, warning
            except Exception as exc:
                LOGGER.exception("dashboard inventory Oracle query failed")
                warning = f"Oracle设备台账查询失败，已使用最近缓存：{exc}"

        cached = self.report_store.list_inventory(filters)
        if cached:
            refreshed_at = max((str(item.get("refreshed_at") or "") for item in cached), default="")
        return cached, "cache", refreshed_at, warning

    def dashboard_summary(self, filters: Mapping[str, str]) -> dict[str, Any]:
        scope = {
            "subcontrolarea": str(filters.get("subcontrolarea") or "").strip(),
            "substation": str(filters.get("substation") or "").strip(),
            "feeder": str(filters.get("feeder") or "").strip(),
            "date_from": str(filters.get("date_from") or "").strip(),
            "date_to": str(filters.get("date_to") or "").strip(),
        }
        # The dashboard has two deliberately different modes:
        #
        # 1) No network scope: show what is already known from the local report
        #    archive only.  This must not query Oracle because an unscoped SMART
        #    inventory query may be large and, more importantly, a history
        #    overview does not need Oracle at all.
        # 2) Area/station/feeder scope present: read the SMART inventory from the
        #    configured source (Oracle is SELECT-only) and merge it with local
        #    report history so that untested devices/completion can be calculated.
        coverage_available = any(scope[key] for key in ("subcontrolarea", "substation", "feeder"))
        latest = self.report_store.latest_device_results(scope)

        source = "history"
        refreshed_at = ""
        warning = ""
        inventory: list[dict[str, Any]] = []
        if coverage_available:
            inventory, source, refreshed_at, warning = self._dashboard_inventory(scope)
        else:
            # Build the initial page entirely from the server-side archive.  The
            # latest final result wins over an older/newer draft, matching the
            # existing dashboard rule that a formally completed report remains
            # the authoritative completed state for that device.
            for state in latest.values():
                if not isinstance(state, Mapping):
                    continue
                final = state.get("final") if isinstance(state.get("final"), Mapping) else None
                draft = state.get("draft") if isinstance(state.get("draft"), Mapping) else None
                row = final or draft
                if not row:
                    continue
                inventory.append(dict(row))

        devices: list[dict[str, Any]] = []
        feeder_totals: dict[str, dict[str, Any]] = {}

        for raw in inventory:
            rmu_name = str(raw.get("rmu_name") or "").strip()
            display_name = str(raw.get("display_name") or raw.get("adms_gss_fid") or rmu_name).strip()
            state = latest.get(display_name.upper(), {}) if display_name else {}
            final = state.get("final") if isinstance(state, Mapping) else None
            draft = state.get("draft") if isinstance(state, Mapping) else None
            if final:
                status = "tested"
                verdict = str(final.get("verdict") or "").strip().lower()
                tested_at = str(final.get("finalized_at") or final.get("updated_at") or final.get("created_at") or "")
                lead = str(final.get("lead") or "")
                report_uuid = str(final.get("report_uuid") or "")
                report_no = str(final.get("report_no") or "")
            elif draft:
                status = "in_progress"
                verdict = ""
                tested_at = str(draft.get("updated_at") or draft.get("created_at") or "")
                lead = str(draft.get("lead") or "")
                report_uuid = str(draft.get("report_uuid") or "")
                report_no = str(draft.get("report_no") or "")
            else:
                status = "untested"
                verdict = ""
                tested_at = ""
                lead = ""
                report_uuid = ""
                report_no = ""
            item = dict(raw)
            item.update({
                "status": status,
                "verdict": verdict,
                "tested_at": tested_at,
                "lead": lead,
                "report_uuid": report_uuid,
                "report_no": report_no,
            })
            devices.append(item)
            feeder_name = str(raw.get("feeder_name") or "(未填写)")
            bucket = feeder_totals.setdefault(feeder_name, {
                "feeder": feeder_name,
                "total": 0,
                "tested": 0,
                "in_progress": 0,
                "untested": 0,
                "passed": 0,
                "conditional": 0,
                "failed": 0,
            })
            bucket["total"] += 1
            if status == "tested":
                bucket["tested"] += 1
                if verdict == "pass":
                    bucket["passed"] += 1
                elif verdict == "conditional":
                    bucket["conditional"] += 1
                elif verdict == "fail":
                    bucket["failed"] += 1
            elif status == "in_progress":
                bucket["in_progress"] += 1
            else:
                bucket["untested"] += 1

        total = len(devices)
        tested = sum(1 for item in devices if item["status"] == "tested")
        in_progress = sum(1 for item in devices if item["status"] == "in_progress")
        # Without a scoped inventory we only know devices that have report
        # history.  Therefore "untested" and "completion rate" are unknown, not
        # zero.  Returning null lets the UI display an em dash instead of a
        # misleading 0 / 100%.
        untested: int | None = total - tested - in_progress if coverage_available else None
        passed = sum(1 for item in devices if item["verdict"] == "pass")
        conditional = sum(1 for item in devices if item["verdict"] == "conditional")
        failed = sum(1 for item in devices if item["verdict"] == "fail")
        completion_rate: float | None = (
            round(tested * 100.0 / total, 1) if coverage_available and total else
            (0.0 if coverage_available else None)
        )
        pass_rate = round(passed * 100.0 / tested, 1) if tested else 0.0
        for bucket in feeder_totals.values():
            if coverage_available:
                bucket["completion_rate"] = round(bucket["tested"] * 100.0 / bucket["total"], 1) if bucket["total"] else 0.0
            else:
                bucket["untested"] = None
                bucket["completion_rate"] = None
            bucket["pass_rate"] = round(bucket["passed"] * 100.0 / bucket["tested"], 1) if bucket["tested"] else 0.0

        return {
            "generated_at": _now(),
            "scope": scope,
            "mode": "coverage" if coverage_available else "history",
            "coverage_available": coverage_available,
            "inventory_source": source,
            "inventory_refreshed_at": refreshed_at,
            "warning": warning,
            "totals": {
                "total": total,
                "tested": tested,
                "in_progress": in_progress,
                "untested": untested,
                "passed": passed,
                "conditional": conditional,
                "failed": failed,
                "completion_rate": completion_rate,
                "pass_rate": pass_rate,
            },
            "feeders": sorted(feeder_totals.values(), key=lambda item: str(item["feeder"])),
            "devices": devices,
        }

    @staticmethod
    def _summary_report_html(summary: Mapping[str, Any], lang: str = "zh") -> str:
        lang = "en" if str(lang).lower() == "en" else "zh"
        is_en = lang == "en"

        def tx(zh: str, en: str) -> str:
            return en if is_en else zh

        def esc(value: Any) -> str:
            return html_lib.escape(str(value if value not in (None, "") else "—"))

        scope = summary.get("scope") if isinstance(summary.get("scope"), Mapping) else {}
        totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
        coverage_available = bool(summary.get("coverage_available"))

        def rate(value: Any) -> str:
            return "—" if value in (None, "") else f"{value}%"

        status_labels = {
            "tested": tx("已调试", "Tested"),
            "in_progress": tx("调试中", "In Progress"),
            "untested": tx("未调试", "Untested"),
        }
        verdict_labels = {
            "pass": tx("通过", "Pass"),
            "conditional": tx("通过（带备注）", "Pass with comments"),
            "fail": tx("失败", "Fail"),
        }

        feeders = summary.get("feeders") if isinstance(summary.get("feeders"), list) else []
        devices = summary.get("devices") if isinstance(summary.get("devices"), list) else []
        no_data = tx("无数据", "No data")
        feeder_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{esc(item.get(key))}</td>"
                for key in ("feeder", "total", "tested", "in_progress", "untested", "passed", "conditional", "failed")
            )
            + f"<td>{esc(rate(item.get('completion_rate')))}</td><td>{esc(rate(item.get('pass_rate')))}</td></tr>"
            for item in feeders if isinstance(item, Mapping)
        ) or f'<tr><td colspan="10">{esc(no_data)}</td></tr>'

        device_rows_parts: list[str] = []
        for item in devices:
            if not isinstance(item, Mapping):
                continue
            values = [
                item.get("subcontrolarea_name"),
                item.get("substation_name"),
                item.get("feeder_name"),
                item.get("display_name"),
                item.get("rmu_type"),
                status_labels.get(str(item.get("status") or ""), item.get("status")),
                verdict_labels.get(str(item.get("verdict") or ""), item.get("verdict")),
                item.get("tested_at"),
                item.get("lead"),
            ]
            device_rows_parts.append("<tr>" + "".join(f"<td>{esc(value)}</td>" for value in values) + "</tr>")
        device_rows = "".join(device_rows_parts) or f'<tr><td colspan="9">{esc(no_data)}</td></tr>'

        cards = [
            (tx("智能设备总数", "Total SMART Devices") if coverage_available else tx("历史测试设备", "Historical Test Devices"), totals.get("total", 0)),
            (tx("已调试", "Tested"), totals.get("tested", 0)),
            (tx("调试中", "In Progress"), totals.get("in_progress", 0)),
            (tx("未调试", "Untested"), totals.get("untested")),
            (tx("通过", "Pass"), totals.get("passed", 0)),
            (tx("通过（带备注）", "Pass with comments"), totals.get("conditional", 0)),
            (tx("失败", "Fail"), totals.get("failed", 0)),
            (tx("完成率", "Completion Rate"), rate(totals.get("completion_rate"))),
            (tx("通过率", "Pass Rate"), rate(totals.get("pass_rate"))),
        ]
        cards_html = "".join(
            f'<div class="card"><span>{esc(key)}</span><strong>{esc(value)}</strong></div>'
            for key, value in cards
        )
        html_lang = "en" if is_en else "zh-CN"
        title = tx("配网 ETE 总体测试报告 · ADMS", "Distribution ETE Overall Test Report · ADMS")
        scope_text = (
            f"{tx('区域', 'Area')}：{esc(scope.get('subcontrolarea'))}　"
            f"{tx('变电站', 'Substation')}：{esc(scope.get('substation'))}　"
            f"{tx('馈线', 'Feeder')}：{esc(scope.get('feeder'))}　"
            f"{tx('统计日期', 'Date Range')}：{esc(scope.get('date_from'))} ~ {esc(scope.get('date_to'))}　"
            f"{tx('生成时间', 'Generated At')}：{esc(summary.get('generated_at'))}"
        )
        feeder_total = tx("总设备", "Total Devices") if coverage_available else tx("历史设备", "Historical Devices")
        return f'''<!doctype html><html lang="{html_lang}"><head><meta charset="utf-8"><title>{esc(title)}</title>
<style>@page{{size:A4 landscape;margin:12mm}}body{{font-family:Arial,"Microsoft YaHei",sans-serif;color:#172a25;font-size:11px}}h1{{color:#0c604b}}.scope{{padding:8px 0 12px;border-bottom:1px solid #ccd8d3}}.cards{{display:grid;grid-template-columns:repeat(9,1fr);gap:6px;margin:12px 0}}.card{{border:1px solid #c9d8d2;background:#eef7f4;padding:8px}}.card span{{display:block;color:#5d6c67;font-size:9px}}.card strong{{font-size:17px}}table{{width:100%;border-collapse:collapse;margin:8px 0 16px;table-layout:fixed}}th,td{{border:1px solid #cbd7d3;padding:5px;text-align:center;word-break:break-word}}th{{background:#dfeee9}}h2{{margin:16px 0 6px}}</style></head><body>
<h1>{esc(title)}</h1>
<div class="scope">{scope_text}</div>
<div class="cards">{cards_html}</div>
<h2>{tx('按馈线统计', 'Statistics by Feeder')}</h2><table><thead><tr><th>{tx('馈线', 'Feeder')}</th><th>{feeder_total}</th><th>{tx('已调试', 'Tested')}</th><th>{tx('调试中', 'In Progress')}</th><th>{tx('未调试', 'Untested')}</th><th>{tx('通过', 'Pass')}</th><th>{tx('通过（带备注）', 'Pass with comments')}</th><th>{tx('失败', 'Fail')}</th><th>{tx('完成率', 'Completion Rate')}</th><th>{tx('通过率', 'Pass Rate')}</th></tr></thead><tbody>{feeder_rows}</tbody></table>
<h2>{tx('设备明细', 'Device Details')}</h2><table><thead><tr><th>{tx('区域', 'Area')}</th><th>{tx('变电站', 'Substation')}</th><th>{tx('馈线', 'Feeder')}</th><th>{tx('设备', 'Device')}</th><th>{tx('类型', 'Type')}</th><th>{tx('状态', 'Status')}</th><th>{tx('总评', 'Overall Result')}</th><th>{tx('调试时间', 'Test Time')}</th><th>{tx('负责人', 'Lead')}</th></tr></thead><tbody>{device_rows}</tbody></table>
</body></html>'''

    def export_dashboard_summary(self, filters: Mapping[str, str], lang: str = "zh") -> dict[str, Any]:
        summary = self.dashboard_summary(filters)
        html_text = self._summary_report_html(summary, lang=lang)
        result = self.report_store.save_summary_report(
            summary,
            html_text,
            software_version=_application_version(),
            pdf_renderer=_render_pdf_with_browser,
        )
        return {**result, "summary": summary}

    def payload(self, network: str, rmu_names: Sequence[str]) -> dict[str, Any]:
        network = "main" if network not in {"main", "distribution"} else network
        # The distribution report is also used as a blank report template.
        # Never load an unfiltered JSON/SQL data source in that state: an
        # empty RMU search must not expose every database row or stale points.
        if network == "distribution" and not rmu_names:
            mappings: list[RmuMapping] = []
            rows: list[Mapping[str, Any]] = []
        else:
            mappings = self.mappings(rmu_names)
            if network == "distribution" and not mappings:
                # A nonexistent RMU is a normal business result, not a server failure.
                # Render the report with an empty mapping so the UI shows "未查询到匹配的设备".
                rows = []
            else:
                if network == "distribution":
                    mappings = self.protocol_mappings(mappings)
                rows = self.signal_rows(network, rmu_names, mappings)

        if network == "distribution":
            # Distribution RMU RTU uses IEC-104 even before an RMU is
            # searched.  Keeping this default aligned with the queried
            # mapping makes the blank first-open page use the same single
            # TCP channel layout as the populated report.
            payload = build_payload(mappings, rows, protocol="IEC-104")
        else:
            payload = copy.deepcopy(self.template_payload)
            payload["points"] = normalize_signals(rows)
            counts: dict[str, int] = {}
            for point in payload["points"]:
                table = point.get("table") or "(未填写)"
                counts[table] = counts.get(table, 0) + 1
            payload["counts"] = counts
            payload["generated_at"] = _now()
            payload.setdefault("meta_defaults", {})["date_from"] = payload["meta_defaults"].get("date_from", "")
            payload.setdefault("meta_defaults", {})["date_to"] = payload["meta_defaults"].get("date_to", "")

        payload["network"] = network
        payload["rmu_names"] = list(rmu_names)
        payload["live_loaded_at"] = _now()
        return payload


def _live_script(
    network: str,
    rmu_names: Sequence[str],
    refresh_seconds: int,
    protocol: str = "IEC 101",
    app_version: str = "unknown",
) -> str:
    rmu_json = json.dumps(",".join(rmu_names), ensure_ascii=False)
    network_json = json.dumps(network, ensure_ascii=False)
    protocol_json = json.dumps(protocol or "IEC 101", ensure_ascii=False)
    app_version_json = json.dumps(app_version or "unknown", ensure_ascii=False)
    return f"""
<!-- distribution-live-script-start -->
<script>
(function () {{
  const initialRmu = {rmu_json};
  const network = {network_json};
  const liveProtocol = {protocol_json};
  const appVersion = {app_version_json};
  const form = document.getElementById('distribution-rmu-form');
  const rmu = document.getElementById('distribution-rmu-input');
  const searchButton = form?.querySelector('.rmu-search-button');
  if (!form || !rmu) return;
  const selectedRmus = initialRmu.split(',').map(v => v.trim()).filter(Boolean);
  const hadSelectedRmusAtLoad = selectedRmus.length > 0;
  rmu.value = '';
  const suggestions = document.getElementById('rmu-suggestions');
  let searchTimer = null;
  let selectedSelector = '';

  function currentLanguage() {{
    if (window.DistributionLanguageController && typeof window.DistributionLanguageController.get === 'function') {{
      return window.DistributionLanguageController.get();
    }}
    if (typeof window.getReportLanguage === 'function') return window.getReportLanguage();
    return document.getElementById('lang-en')?.classList.contains('active') ? 'en' : 'zh';
  }}
  function isEnglish() {{ return currentLanguage() === 'en'; }}
  function liveText(zh, en) {{ return isEnglish() ? en : zh; }}

  function selectionToken(item) {{
    // The row the operator clicked is authoritative. Carry the full displayed
    // FID back to the server and query that exact device. The final segment is
    // still the RMU number/name (for example 6 or 22004), but it is never used
    // alone to expand into another feeder's device.
    const fid = String(item?.adms_gss_fid || '').trim();
    if (fid) return 'fid:' + fid;
    const combinedId = item?.combined_id;
    if (combinedId !== undefined && combinedId !== null && String(combinedId).trim()) {{
      return 'id:' + String(combinedId).trim();
    }}
    return String(item?.rmu_name || '').trim();
  }}

  function navigateSelectedRmus() {{
    // Language is global and persisted independently from device navigation.
    // Do not read, write, or hand off language here.
    const params = new URLSearchParams();
    params.set('network', 'distribution');
    if (selectedRmus.length) params.set('rmu', selectedRmus.join(','));
    // Adding/removing an RMU requires a full page render because the point list
    // comes from a fresh read-only Oracle query. Preserve the current in-memory
    // test through a one-time session handoff so already tested devices are not
    // reset when the new payload is loaded. The handoff is consumed/deleted by
    // the base report immediately after navigation.
    if (hadSelectedRmusAtLoad && selectedRmus.length > 0 &&
        typeof window.prepareRmuNavigationHandoff === 'function') {{
      const handoff = window.prepareRmuNavigationHandoff();
      if (handoff) params.set('handoff', handoff);
    }}
    window.location.assign('/?' + params.toString());
  }}

  function openRmu(selector) {{
    const clean = String(selector || '').trim();
    if (clean && !selectedRmus.includes(clean)) selectedRmus.push(clean);
    // compatibility note: params.set('rmu', name) was the original single-select behavior.
    // The existing query still resolves one RMU at a time; only the URL list is extended at the UI layer.
    navigateSelectedRmus();
  }}

  function removeRmu(name, idAlias) {{
    const clean = String(name || '').trim();
    const oldId = String(idAlias || '').trim();
    let index = selectedRmus.indexOf(clean);
    if (index < 0 && oldId) index = selectedRmus.indexOf(oldId);
    if (index >= 0) selectedRmus.splice(index, 1);
    if (typeof window.setDeviceVerdict === 'function') {{
      window.setDeviceVerdict(clean, '');
      if (oldId) window.setDeviceVerdict(oldId, '');
    }}
    navigateSelectedRmus();
  }}

  function renderSuggestions(items) {{
    if (!suggestions) return;
    suggestions.innerHTML = '';
    if (!items.length) {{
      const empty = document.createElement('div');
      empty.className = 'rmu-suggestion';
      empty.textContent = liveText('未查询到匹配的设备', 'No matching device found');
      suggestions.appendChild(empty);
      suggestions.hidden = false;
      return;
    }}
    items.forEach((item) => {{
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'rmu-suggestion';
      const title = document.createElement('div');
      title.className = 'rmu-suggestion-name';
      title.textContent = item.adms_gss_fid || item.rmu_name;
      const meta = document.createElement('div');
      meta.className = 'rmu-suggestion-meta';
      meta.textContent = [item.rmu_type, item.smart_type, item.nop].filter(Boolean).join(' · ');
      button.append(title, meta);
      button.addEventListener('click', () => {{
        selectedSelector = selectionToken(item);
        rmu.value = item.adms_gss_fid || item.rmu_name;
        suggestions.hidden = true;
        // Add exactly the candidate the operator clicked.  Do not reuse the
        // fuzzy text (for example RMU name "6"), because many feeders can
        // legitimately contain an RMU with the same short name.
        openRmu(selectedSelector);
      }});
      suggestions.appendChild(button);
    }});
    suggestions.hidden = false;
  }}

  async function searchCandidates(value) {{
    if (!value) {{ if (suggestions) suggestions.hidden = true; return []; }}
    try {{
      const response = await fetch('/api/rmu-search?q=' + encodeURIComponent(value), {{cache:'no-store'}});
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || 'search failed');
      const items = Array.isArray(data.items) ? data.items : [];
      renderSuggestions(items);
      return items;
    }} catch (error) {{
      if (suggestions) {{
        suggestions.innerHTML = '';
        const failed = document.createElement('div');
        failed.className = 'rmu-suggestion rmu-suggestion-error';
        console.error('device search failed', error);
        failed.textContent = liveText('设备搜索失败，请查看服务端日志。', 'Device search failed. Please check the server log.');
        suggestions.appendChild(failed);
        suggestions.hidden = false;
      }}
      return [];
    }}
  }}

  rmu.addEventListener('input', () => {{
    selectedSelector = '';
    window.clearTimeout(searchTimer);
    const value = rmu.value.trim();
    searchTimer = window.setTimeout(() => searchCandidates(value), 220);
  }});
  rmu.addEventListener('focus', () => {{
    const value = rmu.value.trim();
    if (value && !selectedSelector) searchCandidates(value);
  }});
  document.addEventListener('click', (event) => {{
    if (suggestions && !form.contains(event.target)) suggestions.hidden = true;
  }});

  form.addEventListener('submit', async (event) => {{
    event.preventDefault();
    const value = rmu.value.trim();
    if (!value) {{
      rmu.focus();
      rmu.classList.add('input-error');
      window.setTimeout(() => rmu.classList.remove('input-error'), 1200);
      return;
    }}
    if (selectedSelector) {{ openRmu(selectedSelector); return; }}
    if (searchButton) {{
      searchButton.disabled = true;
      searchButton.classList.add('is-loading');
      searchButton.setAttribute('aria-busy', 'true');
    }}
    await searchCandidates(value);
    if (searchButton) {{
      searchButton.disabled = false;
      searchButton.classList.remove('is-loading');
      searchButton.removeAttribute('aria-busy');
    }}
  }});

  function deviceVerdicts() {{
    // The base report keeps `state` inside its own IIFE. Access the real report
    // state only through the explicit bridge exported by distribution_report.html.
    if (typeof window.getDeviceVerdicts === 'function') return window.getDeviceVerdicts();
    return {{}};
  }}
  function verdictText(value) {{
    const english = isEnglish();
    if (value === 'pass') return english ? 'Pass' : '通过';
    if (value === 'conditional') return english ? 'Pass with comments' : '通过（带备注）';
    if (value === 'fail') return english ? 'Fail' : '不通过';
    return '—';
  }}
  function syncDeviceVerdicts() {{
    const saved = deviceVerdicts();
    document.querySelectorAll('.device-verdict[data-rmu]').forEach((sel) => {{
      const key = sel.dataset.rmu || '';
      const idKey = sel.dataset.rmuId || '';
      const legacyKey = sel.dataset.rmuLegacy || '';
      if (saved[key] !== undefined) sel.value = saved[key];
      else if (idKey && saved[idKey] !== undefined) {{
        sel.value = saved[idKey];
        if (typeof window.setDeviceVerdict === 'function') {{
          window.setDeviceVerdict(key, saved[idKey]);
          window.setDeviceVerdict(idKey, '');
        }}
      }} else if (legacyKey && saved[legacyKey] !== undefined) {{
        sel.value = saved[legacyKey];
        if (typeof window.setDeviceVerdict === 'function') {{
          window.setDeviceVerdict(key, saved[legacyKey]);
          window.setDeviceVerdict(legacyKey, '');
        }}
      }}
      // This function is intentionally safe to call again after an async
      // History -> Continue Test restore.  Do not register duplicate handlers.
      if (sel.dataset.verdictBound !== '1') {{
        sel.dataset.verdictBound = '1';
        sel.addEventListener('change', () => {{
          if (typeof window.setDeviceVerdict === 'function') window.setDeviceVerdict(key, sel.value);
          else deviceVerdicts()[key] = sel.value;
          syncPrintDeviceVerdicts();
        }});
      }}
    }});
    syncPrintDeviceVerdicts();
  }}
  function syncPrintDeviceVerdicts() {{
    const saved = deviceVerdicts();
    document.querySelectorAll('.print-device-verdict[data-rmu]').forEach((cell) => {{
      const key = cell.dataset.rmu || '';
      const idKey = cell.dataset.rmuId || '';
      const legacyKey = cell.dataset.rmuLegacy || '';
      cell.textContent = verdictText(saved[key] || saved[idKey] || saved[legacyKey] || '');
    }});
  }}
  // Expose explicit synchronizers so the base report can refresh the
  // print-only RMU table after async restore and immediately before printing.
  window.syncDeviceVerdicts = syncDeviceVerdicts;
  window.syncPrintDeviceVerdicts = syncPrintDeviceVerdicts;
  syncDeviceVerdicts();

  document.querySelectorAll('.rmu-remove-button[data-rmu]').forEach((button) => {{
    button.addEventListener('click', () => removeRmu(button.dataset.rmu || '', button.dataset.rmuId || ''));
  }});

  function applyLiveLanguage() {{
    const english = isEnglish();
    document.querySelectorAll('[data-live-zh]').forEach((node) => {{ node.style.display = english ? 'none' : ''; }});
    document.querySelectorAll('[data-live-en]').forEach((node) => {{ node.style.display = english ? '' : 'none'; }});
    const rmuInput = document.getElementById('distribution-rmu-input');
    if (rmuInput) rmuInput.placeholder = english ? 'e.g. enter a device name or number and select a device' : '例如：输入设备名称或编号后选择设备';
    document.querySelectorAll('.device-verdict option[data-label-zh][data-label-en]').forEach((option) => {{
      option.textContent = english ? option.dataset.labelEn : option.dataset.labelZh;
    }});
    if (searchButton) searchButton.setAttribute('aria-label', english ? 'Search Database' : '搜索数据库');
  }}
  window.applyLiveLanguage = applyLiveLanguage;
  window.addEventListener('report-language-change', applyLiveLanguage);

  function applyIec104Layout() {{
    const normalizedProtocol = String(liveProtocol).toUpperCase().replace(/[\\s-]/g, '');
    if (network !== 'distribution' || !normalizedProtocol.includes('104')) return;
    const serialParameterKeys = new Set(['chPort', 'chNote', 'chBaud', 'chDataBits', 'chParity', 'chStopBits']);
    document.querySelectorAll('#channel-table tbody tr').forEach((row) => {{
      const key = row.querySelector('[data-i18n]')?.getAttribute('data-i18n');
      if (serialParameterKeys.has(key)) row.style.display = 'none';
      if (row.cells.length > 2) row.deleteCell(row.cells.length - 1);
    }});
    document.querySelector('#channel-table thead th[data-i18n="colBackup"]')?.remove();
    if (typeof state !== 'undefined' && state.meta) {{
      if (!state.meta.channel || typeof state.meta.channel !== 'object') state.meta.channel = {{}};
      state.meta.channel.single = true;
    }}
  }}

  function applyLiveProtocol() {{
    if (network !== 'distribution' || !liveProtocol || typeof I18N === 'undefined') return;
    I18N.zh.hdrTitle = '配网设备信号端到端测试报告 · ADMS';
    I18N.zh.hdrSub = (s, id, t) => `配网设备 · 版本 v${{appVersion}} · 生成 ${{t}}`;
    I18N.zh.printTitle = '配网设备信号端到端测试报告';
    I18N.zh.secEnv = '配网设备环境与前置条件';
    I18N.zh.secStats = 'RTU 信号测试统计';
    I18N.zh.secPoints = 'RTU 信号点表（全量 · 可检索勾选）';
    I18N.zh.secPointsPrint = 'RTU 信号测试明细（已勾选 / 已填结果）';
    I18N.en.hdrTitle = 'Distribution Equipment Signal End-to-End Test Report · ADMS';
    I18N.en.hdrSub = (s, id, t) => `Distribution Equipment · Version v${{appVersion}} · Generated ${{t}}`;
    I18N.en.printTitle = 'Distribution Equipment Signal End-to-End Test Report';
    I18N.en.secEnv = 'Distribution Equipment Environment and Preconditions';
    I18N.en.secStats = 'RTU Signal Test Statistics';
    I18N.en.secPoints = 'RTU Signal Point List (all · searchable and selectable)';
    I18N.en.secPointsPrint = 'RTU Signal Test Details (selected / with results)';
    I18N.zh.secChannel = `通道参数（${{liveProtocol}}）`;
    I18N.zh.colPrimary = '通道';
    I18N.zh.chName = 'IP 地址';
    I18N.zh.envE1 = `ADMS 与 RTU/网关机 ${{liveProtocol}} 链路建立`;
    I18N.zh.printChannels = `${{liveProtocol}} 通道`;
    I18N.en.secChannel = `Channel Parameters (${{liveProtocol}})`;
    I18N.en.colPrimary = 'Channel';
    I18N.en.chName = 'IP Address';
    I18N.en.envE1 = `ADMS ↔ RTU/gateway ${{liveProtocol}} link up`;
    I18N.en.printChannels = `${{liveProtocol}} Channels`;
    document.getElementById('btn-sample20')?.remove();
    const checklistHeading = document.querySelector('#env h3[data-i18n="secEnvChecks"]');
    if (checklistHeading) {{
      const checklistTable = checklistHeading.nextElementSibling;
      if (checklistTable?.classList.contains('env-table')) checklistTable.remove();
      checklistHeading.remove();
    }}
    if (typeof state !== 'undefined' && state.meta) {{
      if (!state.meta.channel || typeof state.meta.channel !== 'object') state.meta.channel = {{}};
      state.meta.channel.protocol = liveProtocol;
    }}
    // Do not call setLang here: only the explicit 中文 / EN buttons may
    // change the global language preference.
  }}
  applyLiveProtocol();
  applyIec104Layout();
  applyLiveLanguage();
  ['lang-zh', 'lang-en'].forEach((id) => {{
    document.getElementById(id)?.addEventListener('click', () => window.setTimeout(() => {{ applyLiveLanguage(); syncPrintDeviceVerdicts(); }}, 0));
  }});
  if (network === 'distribution') {{
    const style = document.createElement('style');
    style.textContent = '#tabs button:nth-child(4), #tabs button:nth-child(5) {{ display:none; }}';
    document.head.appendChild(style);
  }}
}})();
</script>
<!-- distribution-live-script-end -->
"""


class ReportHandler(BaseHTTPRequestHandler):
    provider: LiveDataProvider
    config: LiveConfig

    def _send(
        self,
        status: int,
        content_type: str,
        body: bytes,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(str(key), str(value))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: Mapping[str, Any]) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_json_body(self, max_bytes: int = 8 * 1024 * 1024) -> Mapping[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if length <= 0 or length > max_bytes:
            raise ValueError("request body is empty or too large")
        raw = self.rfile.read(length)
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _send_report_file(self, report_uuid: str, kind: str, *, inline: bool = False) -> None:
        path = self.provider.report_store.resolve_report_file(report_uuid, kind)
        if path is None:
            self._send(404, "text/plain; charset=utf-8", b"Report file not found")
            return
        content_types = {
            "pdf": "application/pdf",
            "html": "text/html; charset=utf-8",
            "json": "application/json; charset=utf-8",
        }
        suffix = {"pdf": ".pdf", "html": ".html", "json": ".json"}[kind]
        disposition = "inline" if inline else "attachment"
        filename = f"ETE-{report_uuid}{suffix}"
        self._send(
            200,
            content_types[kind],
            path.read_bytes(),
            {"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

    def _send_summary_file(self, summary_uuid: str, kind: str, *, inline: bool = False) -> None:
        path = self.provider.report_store.resolve_summary_file(summary_uuid, kind)
        if path is None:
            self._send(404, "text/plain; charset=utf-8", b"Summary report file not found")
            return
        content_types = {
            "pdf": "application/pdf",
            "html": "text/html; charset=utf-8",
            "json": "application/json; charset=utf-8",
        }
        suffix = {"pdf": ".pdf", "html": ".html", "json": ".json"}[kind]
        disposition = "inline" if inline else "attachment"
        filename = f"ETE-Summary-{summary_uuid}{suffix}"
        self._send(
            200,
            content_types[kind],
            path.read_bytes(),
            {"Content-Disposition": f'{disposition}; filename="{filename}"'},
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        network = query.get("network", ["distribution"])[0]
        rmu_names = _split_names(query.get("rmu", [os.environ.get("RMU_NAMES", "")])[0])
        try:
            if parsed.path == "/api/health":
                self._json(200, {
                    "ok": True,
                    "oracle_configured": self.provider.oracle_enabled,
                    "archive_database": str(self.provider.report_store.db_path.relative_to(_application_root())).replace("\\", "/"),
                    "time": _now(),
                })
                return
            if parsed.path == "/settings":
                self._send(404, "text/plain; charset=utf-8", b"Oracle configuration is managed on the server.")
                return
            if parsed.path == "/history":
                if not self.provider.history_template:
                    self._send(404, "text/plain; charset=utf-8", b"History template not found")
                    return
                self._send(200, "text/html; charset=utf-8", self.provider.history_template.encode("utf-8"))
                return
            if parsed.path == "/dashboard":
                if not self.provider.dashboard_template:
                    self._send(404, "text/plain; charset=utf-8", b"Dashboard template not found")
                    return
                self._send(200, "text/html; charset=utf-8", self.provider.dashboard_template.encode("utf-8"))
                return
            if parsed.path == "/api/dashboard":
                filters = {key: values[0] for key, values in query.items() if values}
                summary = self.provider.dashboard_summary(filters)
                self._json(200, {"ok": True, **summary})
                return
            summary_download = re.fullmatch(r"/api/summary-reports/([0-9a-fA-F-]+)/download", parsed.path)
            if summary_download:
                kind = query.get("format", ["pdf"])[0].lower()
                if kind not in {"pdf", "html", "json"}:
                    self._json(400, {"ok": False, "error": "unsupported format"})
                    return
                self._send_summary_file(summary_download.group(1), kind, inline=False)
                return
            if parsed.path == "/api/reports":
                filters = {key: values[0] for key, values in query.items() if values}
                items = self.provider.report_store.list_reports(filters)
                self._json(200, {"ok": True, "items": items})
                return
            report_match = re.fullmatch(r"/api/reports/([0-9a-fA-F-]+)", parsed.path)
            if report_match:
                item = self.provider.report_store.get_report(report_match.group(1))
                if item is None:
                    self._json(404, {"ok": False, "error": "report not found"})
                else:
                    self._json(200, {"ok": True, "item": item})
                return
            view_match = re.fullmatch(r"/api/reports/([0-9a-fA-F-]+)/view", parsed.path)
            if view_match:
                report_uuid = view_match.group(1)
                if self.provider.report_store.resolve_report_file(report_uuid, "pdf"):
                    self._send_report_file(report_uuid, "pdf", inline=True)
                else:
                    self._send_report_file(report_uuid, "html", inline=True)
                return
            download_match = re.fullmatch(r"/api/reports/([0-9a-fA-F-]+)/download", parsed.path)
            if download_match:
                kind = query.get("format", ["pdf"])[0].lower()
                if kind not in {"pdf", "html", "json"}:
                    self._json(400, {"ok": False, "error": "unsupported format"})
                    return
                self._send_report_file(download_match.group(1), kind, inline=False)
                return
            if parsed.path == "/api/rmu-search":
                keyword = query.get("q", [""])[0].strip()
                if not keyword:
                    self._json(200, {"ok": True, "items": []})
                    return
                try:
                    items = self.provider.search_rmus(keyword)
                except Exception:
                    LOGGER.exception("RMU partial search failed keyword=%r", keyword)
                    self._json(500, {"ok": False, "error": "环网柜模糊查询失败，请查看服务端日志。", "items": []})
                    return
                self._json(200, {"ok": True, "items": items, "keyword": keyword})
                return
            if parsed.path == "/api/report":
                self._json(200, self.provider.payload(network, rmu_names))
                return
            if parsed.path not in {"/", "/index.html"}:
                self._send(404, "text/plain; charset=utf-8", b"Not found")
                return

            payload = self.provider.payload(network, rmu_names)
            live_protocol = str(
                payload.get("meta_defaults", {}).get("channel", {}).get("protocol") or "IEC 101"
            )
            live_script = _live_script(
                network,
                rmu_names,
                self.config.refresh_seconds,
                live_protocol,
                _application_version(),
            )
            page = render_report_text(
                self.provider.template,
                payload,
                include_mapping=network == "distribution",
                extra_before_body_end=live_script,
                print_password_hash=self.provider.print_password_hash,
                app_version=_application_version(),
            )
            self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
        except Exception:  # request boundary: never drop the HTTP connection silently
            LOGGER.exception("request failed path=%s", parsed.path)
            try:
                self._json(500, {"ok": False, "error": "服务端处理失败，请联系服务管理员查看日志。"})
            except (BrokenPipeError, ConnectionResetError):
                LOGGER.warning("client disconnected while sending error response")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/reports":
                data = self._read_json_body()
                result = self.provider.archive_report(data, self.client_address[0] if self.client_address else "")
                self._json(201, {"ok": True, **result})
                return
            generate_pdf_match = re.fullmatch(r"/api/reports/([0-9a-fA-F-]+)/generate-pdf", parsed.path)
            if generate_pdf_match:
                result = self.provider.generate_report_pdf(generate_pdf_match.group(1))
                self._json(200, {"ok": True, **result})
                return
            if parsed.path == "/api/dashboard/export":
                data = self._read_json_body()
                filters = data.get("filters") if isinstance(data.get("filters"), Mapping) else data
                lang = str(data.get("lang") or "zh") if isinstance(data, Mapping) else "zh"
                result = self.provider.export_dashboard_summary(filters, lang=lang)
                self._json(201, {"ok": True, **result})
                return
            self._send(404, "text/plain; charset=utf-8", b"Not found")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception:
            LOGGER.exception("POST request failed path=%s", parsed.path)
            try:
                self._json(500, {"ok": False, "error": "服务端归档失败，请查看服务端日志。"})
            except (BrokenPipeError, ConnectionResetError):
                LOGGER.warning("client disconnected while sending POST error response")

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("%s", format % args)


def _parse_args() -> LiveConfig:
    parser = argparse.ArgumentParser(description="启动可随时打开的实时信号报告服务")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--main-signals-json", type=Path)
    parser.add_argument("--distribution-signals-json", type=Path)
    parser.add_argument("--mapping-json", type=Path)
    parser.add_argument("--mapping-sql", type=Path)
    parser.add_argument("--main-signal-sql", type=Path)
    parser.add_argument("--distribution-signal-sql", type=Path)
    parser.add_argument("--distribution-point-sql", type=Path)
    parser.add_argument("--distribution-protocol-sql", type=Path)
    parser.add_argument("--refresh-seconds", type=int, default=60)
    args = parser.parse_args()
    return LiveConfig(
        template=args.template,
        host=args.host,
        port=args.port,
        main_signals_json=args.main_signals_json,
        distribution_signals_json=args.distribution_signals_json,
        mapping_json=args.mapping_json,
        main_signal_sql=args.main_signal_sql,
        distribution_signal_sql=args.distribution_signal_sql,
        refresh_seconds=max(10, args.refresh_seconds),
        mapping_sql=args.mapping_sql,
        distribution_point_sql=args.distribution_point_sql,
        distribution_protocol_sql=args.distribution_protocol_sql,
    )


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = _parse_args()
    provider = LiveDataProvider(config)
    handler = type("ConfiguredReportHandler", (ReportHandler,), {})
    handler.provider = provider
    handler.config = config
    server = ThreadingHTTPServer((config.host, config.port), handler)
    LOGGER.info("live report listening on http://%s:%s/", config.host, config.port)
    LOGGER.info("network=distribution; config_source=report_config.json; oracle_credentials=server_config; oracle_access=STRICT_READ_ONLY")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("service stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InputError, OSError) as exc:
        raise SystemExit(f"错误：{exc}")
