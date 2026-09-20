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
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from distribution_signal_verifier.distribution_signal_verifier import (
    DEFAULT_TEMPLATE,
    InputError,
    RmuMapping,
    build_payload,
    build_distribution_point_sql,
    build_distribution_protocol_sql,
    build_rmu_search_sql,
    load_json_rows,
    normalize_mapping,
    normalize_signals,
    query_rmu_mapping,
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
                wanted = {name.strip() for name in rmu_names}
                mappings = [item for item in mappings if item.rmu_name in wanted]
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
            ids = [item.combined_id for item in mappings if item.combined_id not in (None, "")]
            if not ids:
                return []
            return self._sql_rows(self.config.distribution_point_sql, "combined_id", ids)
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
                "rmu_name": m.rmu_name,
                "adms_gss_fid": m.adms_gss_fid,
                "rmu_type": m.rmu_type,
                "smart_type": m.smart_type,
                "nop": m.nop,
            }
            for m in matches[:limit]
        ]

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
                # Render the report with an empty mapping so the UI shows "未查询到匹配的环网柜".
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
) -> str:
    rmu_json = json.dumps(",".join(rmu_names), ensure_ascii=False)
    network_json = json.dumps(network, ensure_ascii=False)
    protocol_json = json.dumps(protocol or "IEC 101", ensure_ascii=False)
    return f"""
<!-- distribution-live-script-start -->
<script>
(function () {{
  const initialRmu = {rmu_json};
  const network = {network_json};
  const liveProtocol = {protocol_json};
  const form = document.getElementById('distribution-rmu-form');
  const rmu = document.getElementById('distribution-rmu-input');
  const searchButton = form?.querySelector('.rmu-search-button');
  if (!form || !rmu) return;
  rmu.value = initialRmu;
  const suggestions = document.getElementById('rmu-suggestions');
  let searchTimer = null;
  let selectedRmu = initialRmu;

  function openRmu(name) {{
    const params = new URLSearchParams();
    params.set('network', 'distribution');
    params.set('rmu', name);
    window.location.assign('/?' + params.toString());
  }}

  function renderSuggestions(items) {{
    if (!suggestions) return;
    suggestions.innerHTML = '';
    if (!items.length) {{
      const empty = document.createElement('div');
      empty.className = 'rmu-suggestion';
      empty.textContent = document.getElementById('lang-en')?.classList.contains('active')
        ? 'No matching RMU found' : '未查询到匹配的环网柜';
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
        selectedRmu = item.rmu_name;
        rmu.value = item.rmu_name;
        suggestions.hidden = true;
        openRmu(item.rmu_name);
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
        failed.textContent = (document.getElementById('lang-en')?.classList.contains('active')
          ? 'RMU search failed: ' : '环网柜搜索失败：') + (error?.message || 'unknown error');
        suggestions.appendChild(failed);
        suggestions.hidden = false;
      }}
      return [];
    }}
  }}

  rmu.addEventListener('input', () => {{
    selectedRmu = '';
    window.clearTimeout(searchTimer);
    const value = rmu.value.trim();
    searchTimer = window.setTimeout(() => searchCandidates(value), 220);
  }});
  rmu.addEventListener('focus', () => {{
    const value = rmu.value.trim();
    if (value && !selectedRmu) searchCandidates(value);
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
    if (selectedRmu && value === selectedRmu) {{ openRmu(selectedRmu); return; }}
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

  function applyLiveLanguage() {{
    const english = document.getElementById('lang-en')?.classList.contains('active');
    document.querySelectorAll('[data-live-zh]').forEach((node) => {{ node.style.display = english ? 'none' : ''; }});
    document.querySelectorAll('[data-live-en]').forEach((node) => {{ node.style.display = english ? '' : 'none'; }});
    const rmuInput = document.getElementById('distribution-rmu-input');
    if (rmuInput) rmuInput.placeholder = english ? 'e.g. type 346 and select an RMU' : '例如：输入 346 后选择环网柜';
  }}

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
    I18N.zh.hdrSub = (s, id, t) => `配网设备 · 变电站 ${{s}} · 区域 ${{id}} · 生成 ${{t}}`;
    I18N.zh.printTitle = '配网设备信号端到端测试报告';
    I18N.zh.secEnv = '配网设备环境与前置条件';
    I18N.zh.secStats = 'RTU 信号测试统计';
    I18N.zh.secPoints = 'RTU 信号点表（全量 · 可检索勾选）';
    I18N.zh.secPointsPrint = 'RTU 信号测试明细（已勾选 / 已填结果）';
    I18N.en.hdrTitle = 'Distribution Equipment Signal End-to-End Test Report · ADMS';
    I18N.en.hdrSub = (s, id, t) => `Distribution Equipment · Substation ${{s}} · Area ${{id}} · Generated ${{t}}`;
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
    if (typeof setLang === 'function' && typeof lang !== 'undefined') setLang(lang);
  }}
  applyLiveProtocol();
  applyIec104Layout();
  applyLiveLanguage();
  ['lang-zh', 'lang-en'].forEach((id) => {{
    document.getElementById(id)?.addEventListener('click', () => window.setTimeout(applyLiveLanguage, 0));
  }});
  if (network === 'distribution') {{
    const style = document.createElement('style');
    style.textContent = '#tabs button:nth-child(4), #tabs button:nth-child(5) {{ display:none; }}';
    document.head.appendChild(style);
  }}
  window.setTimeout(() => {{ if (!document.hidden) window.location.reload(); }}, {refresh_seconds} * 1000);
}})();
</script>
<!-- distribution-live-script-end -->
"""


class ReportHandler(BaseHTTPRequestHandler):
    provider: LiveDataProvider
    config: LiveConfig

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: Mapping[str, Any]) -> None:
        self._send(status, "application/json; charset=utf-8", json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        network = query.get("network", ["distribution"])[0]
        rmu_names = _split_names(query.get("rmu", [os.environ.get("RMU_NAMES", "")])[0])
        try:
            if parsed.path == "/api/health":
                self._json(200, {"ok": True, "oracle_configured": self.provider.oracle_enabled, "time": _now()})
                return
            if parsed.path == "/settings":
                self._send(404, "text/plain; charset=utf-8", b"Oracle configuration is managed on the server.")
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
            live_script = _live_script(network, rmu_names, self.config.refresh_seconds, live_protocol)
            page = render_report_text(
                self.provider.template,
                payload,
                include_mapping=network == "distribution",
                extra_before_body_end=live_script,
                print_password_hash=self.provider.print_password_hash,
            )
            self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))
        except Exception:  # request boundary: never drop the HTTP connection silently
            # Keep Oracle driver details, DSNs, hostnames, and other server
            # diagnostics in the service log only.  Returning a real HTTP 500
            # avoids browser ERR_EMPTY_RESPONSE when a packaged dependency or
            # database connection fails unexpectedly.
            LOGGER.exception("request failed path=%s", parsed.path)
            try:
                self._json(500, {"ok": False, "error": "服务端处理失败，请联系服务管理员查看日志。"})
            except (BrokenPipeError, ConnectionResetError):
                LOGGER.warning("client disconnected while sending error response")

    def do_POST(self) -> None:  # noqa: N802
        self._send(404, "text/plain; charset=utf-8", b"Oracle configuration is managed on the server.")

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
    LOGGER.info("network=distribution; config_source=report_config.json; oracle_credentials=server_config")
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