"""Persistent archive for Distribution ETE reports.

All durable runtime data lives below ``<application root>/data`` so the whole
application can still be managed as one directory.  Code upgrades must preserve
that data directory.  SQLite is accessed only by the HTTP service; browser
clients never open the database file directly.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


SCHEMA_VERSION = 3


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _now_local() -> datetime:
    return datetime.now().astimezone()


class ReportStore:
    """SQLite metadata + immutable report files under the application data dir."""

    def __init__(self, application_root: Path):
        self.application_root = Path(application_root).resolve()
        self.data_root = self.application_root / "data"
        self.database_dir = self.data_root / "database"
        self.reports_dir = self.data_root / "reports"
        self.summary_reports_dir = self.data_root / "summary_reports"
        self.backup_dir = self.data_root / "backup"
        self.db_backup_dir = self.backup_dir / "database"
        self.db_path = self.database_dir / "ete_reports.db"
        self._migration_lock = threading.Lock()
        self._ensure_directories()
        self._migrate()

    def _ensure_directories(self) -> None:
        for path in (
            self.data_root,
            self.database_dir,
            self.reports_dir,
            self.summary_reports_dir,
            self.backup_dir,
            self.db_backup_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=8.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=8000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _current_schema_version(self, connection: sqlite3.Connection) -> int:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        return int(row["version"] or 0)

    def _backup_database(self, source: sqlite3.Connection, target_version: int) -> None:
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return
        stamp = _now_local().strftime("%Y%m%d-%H%M%S")
        target = self.db_backup_dir / f"ete_reports-before-v{target_version}-{stamp}.db"
        backup = sqlite3.connect(target)
        try:
            source.backup(backup)
        finally:
            backup.close()

    def _migrate(self) -> None:
        with self._migration_lock:
            connection = self._connect()
            try:
                current = self._current_schema_version(connection)
                if current >= SCHEMA_VERSION:
                    return
                if current > 0:
                    self._backup_database(connection, SCHEMA_VERSION)
                if current < 1:
                    self._migration_v1(connection)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (1, _now_local().isoformat(timespec="seconds")),
                    )
                    current = 1
                if current < 2:
                    self._migration_v2(connection)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (2, _now_local().isoformat(timespec="seconds")),
                    )
                    current = 2
                if current < 3:
                    self._migration_v3(connection)
                    connection.execute(
                        "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                        (3, _now_local().isoformat(timespec="seconds")),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _migration_v1(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_uuid TEXT PRIMARY KEY,
                report_no TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                test_date_from TEXT NOT NULL DEFAULT '',
                test_date_to TEXT NOT NULL DEFAULT '',
                phase TEXT NOT NULL DEFAULT '',
                lead TEXT NOT NULL DEFAULT '',
                testers TEXT NOT NULL DEFAULT '',
                adms_version TEXT NOT NULL DEFAULT '',
                verdict_summary TEXT NOT NULL DEFAULT '',
                is_draft INTEGER NOT NULL DEFAULT 0,
                device_count INTEGER NOT NULL DEFAULT 0,
                software_version TEXT NOT NULL DEFAULT '',
                client_ip TEXT NOT NULL DEFAULT '',
                pdf_path TEXT NOT NULL DEFAULT '',
                html_path TEXT NOT NULL DEFAULT '',
                snapshot_path TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS report_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_uuid TEXT NOT NULL,
                seq INTEGER NOT NULL,
                rmu_name TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                rmu_type TEXT NOT NULL DEFAULT '',
                smart_type TEXT NOT NULL DEFAULT '',
                nop TEXT NOT NULL DEFAULT '',
                function_location TEXT NOT NULL DEFAULT '',
                ip TEXT NOT NULL DEFAULT '',
                protocol TEXT NOT NULL DEFAULT '',
                feeder_name TEXT NOT NULL DEFAULT '',
                substation_name TEXT NOT NULL DEFAULT '',
                subcontrolarea_name TEXT NOT NULL DEFAULT '',
                verdict TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(report_uuid) REFERENCES reports(report_uuid) ON DELETE CASCADE,
                UNIQUE(report_uuid, seq)
            );

            CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_reports_test_dates ON reports(test_date_from, test_date_to);
            CREATE INDEX IF NOT EXISTS idx_reports_lead ON reports(lead);
            CREATE INDEX IF NOT EXISTS idx_report_devices_rmu ON report_devices(rmu_name);
            CREATE INDEX IF NOT EXISTS idx_report_devices_display ON report_devices(display_name);
            CREATE INDEX IF NOT EXISTS idx_report_devices_substation ON report_devices(substation_name);
            CREATE INDEX IF NOT EXISTS idx_report_devices_feeder ON report_devices(feeder_name);
            """
        )

    @staticmethod
    def _migration_v2(connection: sqlite3.Connection) -> None:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(reports)").fetchall()}
        if "updated_at" not in columns:
            connection.execute("ALTER TABLE reports ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        if "finalized_at" not in columns:
            connection.execute("ALTER TABLE reports ADD COLUMN finalized_at TEXT NOT NULL DEFAULT ''")
        connection.execute("UPDATE reports SET updated_at=created_at WHERE COALESCE(updated_at, '')='' ")
        connection.execute(
            "UPDATE reports SET finalized_at=created_at WHERE is_draft=0 AND COALESCE(finalized_at, '')=''"
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_updated_at ON reports(updated_at DESC)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(is_draft)")

    @staticmethod
    def _migration_v3(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS inventory_devices (
                device_key TEXT PRIMARY KEY,
                combined_id TEXT NOT NULL DEFAULT '',
                rmu_name TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                rmu_type TEXT NOT NULL DEFAULT '',
                smart_type TEXT NOT NULL DEFAULT '',
                nop TEXT NOT NULL DEFAULT '',
                function_location TEXT NOT NULL DEFAULT '',
                feeder_name TEXT NOT NULL DEFAULT '',
                substation_name TEXT NOT NULL DEFAULT '',
                subcontrolarea_name TEXT NOT NULL DEFAULT '',
                refreshed_at TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_inventory_rmu ON inventory_devices(rmu_name);
            CREATE INDEX IF NOT EXISTS idx_inventory_substation ON inventory_devices(substation_name);
            CREATE INDEX IF NOT EXISTS idx_inventory_feeder ON inventory_devices(feeder_name);
            CREATE INDEX IF NOT EXISTS idx_inventory_area ON inventory_devices(subcontrolarea_name);

            CREATE TABLE IF NOT EXISTS summary_reports (
                summary_uuid TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                subcontrolarea TEXT NOT NULL DEFAULT '',
                substation TEXT NOT NULL DEFAULT '',
                feeder TEXT NOT NULL DEFAULT '',
                date_from TEXT NOT NULL DEFAULT '',
                date_to TEXT NOT NULL DEFAULT '',
                total_devices INTEGER NOT NULL DEFAULT 0,
                tested_devices INTEGER NOT NULL DEFAULT 0,
                passed_devices INTEGER NOT NULL DEFAULT 0,
                failed_devices INTEGER NOT NULL DEFAULT 0,
                completion_rate REAL NOT NULL DEFAULT 0,
                pass_rate REAL NOT NULL DEFAULT 0,
                software_version TEXT NOT NULL DEFAULT '',
                pdf_path TEXT NOT NULL DEFAULT '',
                html_path TEXT NOT NULL DEFAULT '',
                snapshot_path TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_summary_created_at ON summary_reports(created_at DESC);
            """
        )

    @staticmethod
    def _device_verdict_value(device_verdicts: Mapping[str, Any], device: Mapping[str, Any]) -> str:
        """Resolve one device verdict by exact identity before legacy short name.

        New UI state keys verdicts by the operator-selected full ADMS GSS FID.
        Falling back to the short RMU name is kept only for old archives.
        """
        rmu_name = _text(device.get("rmu_name"))
        display_name = _text(device.get("adms_gss_fid") or device.get("display_name"))
        combined_id = _text(device.get("combined_id"))
        candidates = []
        if display_name:
            candidates.extend((f"fid:{display_name}", display_name))
        if combined_id:
            candidates.extend((f"id:{combined_id}", combined_id))
        if rmu_name:
            candidates.append(rmu_name)
        for key in candidates:
            value = _text(device_verdicts.get(key))
            if value:
                return value
        return ""

    @classmethod
    def _summary_verdict(cls, device_verdicts: Mapping[str, Any], devices: Sequence[Mapping[str, Any]]) -> str:
        values = [cls._device_verdict_value(device_verdicts, item) for item in devices]
        values = [value for value in values if value]
        if not values:
            return ""
        if "fail" in values:
            return "fail"
        if "conditional" in values:
            return "conditional"
        if all(value == "pass" for value in values):
            return "pass"
        return ",".join(sorted(set(values)))

    @staticmethod
    def _write_text_atomic(path: Path, text: str) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(text, encoding="utf-8")
        temp.replace(path)

    def save_report(
        self,
        payload: Mapping[str, Any],
        *,
        client_ip: str = "",
        software_version: str = "",
        pdf_renderer: Callable[[Path, Path], bool] | None = None,
    ) -> dict[str, Any]:
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, Mapping):
            raise ValueError("snapshot is required")
        html_text = payload.get("html")
        if not isinstance(html_text, str) or "<html" not in html_text.lower():
            raise ValueError("print HTML snapshot is required")

        meta = snapshot.get("meta") if isinstance(snapshot.get("meta"), Mapping) else {}
        devices_raw = snapshot.get("distribution_mappings")
        devices: list[Mapping[str, Any]] = [item for item in devices_raw if isinstance(item, Mapping)] if isinstance(devices_raw, list) else []
        verdicts = meta.get("device_verdicts") if isinstance(meta.get("device_verdicts"), Mapping) else {}
        is_draft = bool(payload.get("is_draft"))

        requested_uuid = _text(payload.get("report_uuid"))
        if requested_uuid:
            try:
                requested_uuid = str(uuid.UUID(requested_uuid))
            except ValueError:
                requested_uuid = ""

        connection = self._connect()
        try:
            existing = None
            if requested_uuid:
                row = connection.execute("SELECT * FROM reports WHERE report_uuid=?", (requested_uuid,)).fetchone()
                existing = dict(row) if row is not None else None
        finally:
            connection.close()

        now = _now_local()
        updated_at = now.isoformat(timespec="seconds")
        if existing:
            report_uuid = str(existing["report_uuid"])
            created_at = _text(existing.get("created_at")) or updated_at
            snapshot_rel = _text(existing.get("snapshot_path"))
            if snapshot_rel:
                report_dir = (self.application_root / snapshot_rel).resolve().parent
            else:
                created_dt = datetime.fromisoformat(created_at)
                report_dir = self.reports_dir / created_dt.strftime("%Y") / created_dt.strftime("%m") / created_dt.strftime("%d") / report_uuid
            finalized_at = _text(existing.get("finalized_at"))
        else:
            report_uuid = str(uuid.uuid4())
            created_at = updated_at
            report_dir = self.reports_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d") / report_uuid
            report_dir.mkdir(parents=True, exist_ok=False)
            finalized_at = ""

        report_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = report_dir / "snapshot.json"
        html_path = report_dir / "report.html"
        pdf_path = report_dir / "report.pdf"

        if not is_draft:
            finalized_at = updated_at

        snapshot_doc = dict(snapshot)
        snapshot_doc["archive"] = {
            "report_uuid": report_uuid,
            "created_at": created_at,
            "updated_at": updated_at,
            "finalized_at": finalized_at,
            "status": "draft" if is_draft else "final",
            "software_version": software_version,
            "client_ip": client_ip,
        }
        self._write_text_atomic(snapshot_path, json.dumps(snapshot_doc, ensure_ascii=False, indent=2))
        self._write_text_atomic(html_path, html_text)

        pdf_saved = False
        if not is_draft and pdf_renderer is not None:
            try:
                pdf_saved = bool(pdf_renderer(html_path, pdf_path)) and pdf_path.exists() and pdf_path.stat().st_size > 0
            except Exception:
                pdf_saved = False
        if not pdf_saved and pdf_path.exists():
            pdf_path.unlink(missing_ok=True)

        verdict_summary = self._summary_verdict(verdicts, devices)
        report_no = _text(meta.get("report_id"))
        relative = lambda p: str(p.relative_to(self.application_root)).replace("\\", "/")
        connection = self._connect()
        try:
            if existing:
                connection.execute(
                    """
                    UPDATE reports SET
                        report_no=?, updated_at=?, test_date_from=?, test_date_to=?,
                        phase=?, lead=?, testers=?, adms_version=?, verdict_summary=?, is_draft=?,
                        device_count=?, software_version=?, client_ip=?, pdf_path=?, html_path=?,
                        snapshot_path=?, finalized_at=?
                    WHERE report_uuid=?
                    """,
                    (
                        report_no, updated_at, _text(meta.get("date_from")), _text(meta.get("date_to")),
                        _text(meta.get("phase")), _text(meta.get("lead")), _text(meta.get("testers")),
                        _text(meta.get("adms_version")), verdict_summary, 1 if is_draft else 0,
                        len(devices), software_version, client_ip, relative(pdf_path) if pdf_saved else "",
                        relative(html_path), relative(snapshot_path), finalized_at, report_uuid,
                    ),
                )
                connection.execute("DELETE FROM report_devices WHERE report_uuid=?", (report_uuid,))
            else:
                connection.execute(
                    """
                    INSERT INTO reports(
                        report_uuid, report_no, created_at, test_date_from, test_date_to,
                        phase, lead, testers, adms_version, verdict_summary, is_draft,
                        device_count, software_version, client_ip, pdf_path, html_path, snapshot_path,
                        updated_at, finalized_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_uuid, report_no, created_at, _text(meta.get("date_from")),
                        _text(meta.get("date_to")), _text(meta.get("phase")), _text(meta.get("lead")),
                        _text(meta.get("testers")), _text(meta.get("adms_version")), verdict_summary,
                        1 if is_draft else 0, len(devices), software_version, client_ip,
                        relative(pdf_path) if pdf_saved else "", relative(html_path), relative(snapshot_path),
                        updated_at, finalized_at,
                    ),
                )
            for seq, device in enumerate(devices, 1):
                rmu_name = _text(device.get("rmu_name"))
                connection.execute(
                    """
                    INSERT INTO report_devices(
                        report_uuid, seq, rmu_name, display_name, rmu_type, smart_type,
                        nop, function_location, ip, protocol, feeder_name,
                        substation_name, subcontrolarea_name, verdict
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_uuid, seq, rmu_name, _text(device.get("adms_gss_fid") or rmu_name),
                        _text(device.get("rmu_type")), _text(device.get("smart_type")),
                        _text(device.get("nop")), _text(device.get("function_location")),
                        _text(device.get("ip")), _text(device.get("protocol_name")),
                        _text(device.get("feeder_name")), _text(device.get("substation_name")),
                        _text(device.get("subcontrolarea_name")), self._device_verdict_value(verdicts, device),
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            if not existing:
                shutil.rmtree(report_dir, ignore_errors=True)
            raise
        finally:
            connection.close()

        return {
            "report_uuid": report_uuid,
            "report_no": report_no,
            "created_at": created_at,
            "updated_at": updated_at,
            "finalized_at": finalized_at,
            "is_draft": is_draft,
            "pdf_saved": pdf_saved,
            "device_count": len(devices),
        }

    def register_report_pdf(self, report_uuid: str, pdf_path: Path) -> dict[str, Any]:
        """Attach a generated PDF without changing the report workflow status."""
        resolved = Path(pdf_path).resolve()
        try:
            resolved.relative_to(self.data_root.resolve())
        except ValueError as exc:
            raise ValueError("PDF path must be inside the report data directory") from exc
        if not resolved.is_file() or resolved.stat().st_size <= 0:
            raise ValueError("generated PDF file is missing or empty")

        relative = str(resolved.relative_to(self.application_root)).replace("\\", "/")
        connection = self._connect()
        try:
            cursor = connection.execute(
                "UPDATE reports SET pdf_path=? WHERE report_uuid=?",
                (relative, report_uuid),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ValueError("report not found")
            connection.commit()
        finally:
            connection.close()

        report = self.get_report(report_uuid)
        if report is None:
            raise ValueError("report not found")
        return report

    def list_reports(self, filters: Mapping[str, str], limit: int = 300) -> list[dict[str, Any]]:
        clauses = ["1=1"]
        params: list[Any] = []
        date_from = _text(filters.get("date_from"))
        date_to = _text(filters.get("date_to"))
        device = _text(filters.get("device"))
        substation = _text(filters.get("substation"))
        feeder = _text(filters.get("feeder"))
        lead = _text(filters.get("lead"))
        verdict = _text(filters.get("verdict"))
        status = _text(filters.get("status")).lower()
        if date_from:
            clauses.append("COALESCE(r.test_date_to, '') >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("COALESCE(r.test_date_from, '') <= ?")
            params.append(date_to)
        if lead:
            clauses.append("UPPER(r.lead) LIKE UPPER(?)")
            params.append(f"%{lead}%")
        if verdict:
            clauses.append("r.verdict_summary = ?")
            params.append(verdict)
        if status == "draft":
            clauses.append("r.is_draft = 1")
        elif status == "final":
            clauses.append("r.is_draft = 0")
        if device:
            clauses.append(
                "EXISTS (SELECT 1 FROM report_devices d WHERE d.report_uuid=r.report_uuid "
                "AND (UPPER(d.rmu_name) LIKE UPPER(?) OR UPPER(d.display_name) LIKE UPPER(?)))"
            )
            params.extend([f"%{device}%", f"%{device}%"])
        if substation:
            clauses.append(
                "EXISTS (SELECT 1 FROM report_devices d WHERE d.report_uuid=r.report_uuid AND UPPER(d.substation_name) LIKE UPPER(?))"
            )
            params.append(f"%{substation}%")
        if feeder:
            clauses.append(
                "EXISTS (SELECT 1 FROM report_devices d WHERE d.report_uuid=r.report_uuid AND UPPER(d.feeder_name) LIKE UPPER(?))"
            )
            params.append(f"%{feeder}%")

        sql = f"""
            SELECT r.* FROM reports r
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(NULLIF(r.updated_at, ''), r.created_at) DESC
            LIMIT ?
        """
        params.append(max(1, min(int(limit), 1000)))
        connection = self._connect()
        try:
            report_rows = [dict(row) for row in connection.execute(sql, params).fetchall()]
            for report in report_rows:
                devices = [
                    dict(row)
                    for row in connection.execute(
                        "SELECT * FROM report_devices WHERE report_uuid=? ORDER BY seq",
                        (report["report_uuid"],),
                    ).fetchall()
                ]
                report["devices"] = devices
                report["pdf_available"] = bool(report.get("pdf_path"))
            return report_rows
        finally:
            connection.close()

    def get_report(self, report_uuid: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM reports WHERE report_uuid=?", (report_uuid,)).fetchone()
            if row is None:
                return None
            report = dict(row)
            report["devices"] = [
                dict(item)
                for item in connection.execute(
                    "SELECT * FROM report_devices WHERE report_uuid=? ORDER BY seq", (report_uuid,)
                ).fetchall()
            ]
            report["pdf_available"] = bool(report.get("pdf_path"))
            return report
        finally:
            connection.close()

    @staticmethod
    def _inventory_key(device: Mapping[str, Any]) -> str:
        combined = _text(device.get("combined_id"))
        if combined:
            return f"id:{combined}"
        return "name:" + "|".join(
            _text(device.get(key)).upper()
            for key in ("subcontrolarea_name", "substation_name", "feeder_name", "rmu_name")
        )

    def upsert_inventory(self, devices: Sequence[Mapping[str, Any]]) -> str:
        """Persist the last known SMART-device inventory for offline dashboard use."""
        refreshed_at = _now_local().isoformat(timespec="seconds")
        connection = self._connect()
        try:
            for device in devices:
                key = self._inventory_key(device)
                connection.execute(
                    """
                    INSERT INTO inventory_devices(
                        device_key, combined_id, rmu_name, display_name, rmu_type, smart_type,
                        nop, function_location, feeder_name, substation_name,
                        subcontrolarea_name, refreshed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(device_key) DO UPDATE SET
                        combined_id=excluded.combined_id,
                        rmu_name=excluded.rmu_name,
                        display_name=excluded.display_name,
                        rmu_type=excluded.rmu_type,
                        smart_type=excluded.smart_type,
                        nop=excluded.nop,
                        function_location=excluded.function_location,
                        feeder_name=excluded.feeder_name,
                        substation_name=excluded.substation_name,
                        subcontrolarea_name=excluded.subcontrolarea_name,
                        refreshed_at=excluded.refreshed_at
                    """,
                    (
                        key, _text(device.get("combined_id")), _text(device.get("rmu_name")),
                        _text(device.get("display_name") or device.get("adms_gss_fid")),
                        _text(device.get("rmu_type")), _text(device.get("smart_type")),
                        _text(device.get("nop")), _text(device.get("function_location")),
                        _text(device.get("feeder_name")), _text(device.get("substation_name")),
                        _text(device.get("subcontrolarea_name")), refreshed_at,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return refreshed_at

    def list_inventory(self, filters: Mapping[str, str]) -> list[dict[str, Any]]:
        clauses = ["UPPER(COALESCE(smart_type, '')) = 'SMART'"]
        params: list[Any] = []
        for field, key in (
            ("subcontrolarea_name", "subcontrolarea"),
            ("substation_name", "substation"),
            ("feeder_name", "feeder"),
        ):
            value = _text(filters.get(key))
            if value:
                clauses.append(f"UPPER({field}) LIKE UPPER(?)")
                params.append(f"%{value}%")
        connection = self._connect()
        try:
            return [
                dict(row)
                for row in connection.execute(
                    f"SELECT * FROM inventory_devices WHERE {' AND '.join(clauses)} "
                    "ORDER BY subcontrolarea_name, substation_name, feeder_name, rmu_name",
                    params,
                ).fetchall()
            ]
        finally:
            connection.close()

    def latest_device_results(self, filters: Mapping[str, str]) -> dict[str, dict[str, Any]]:
        """Return latest final and draft record per RMU for dashboard aggregation."""
        clauses = ["1=1"]
        params: list[Any] = []
        date_from = _text(filters.get("date_from"))
        date_to = _text(filters.get("date_to"))
        if date_from:
            clauses.append("COALESCE(r.test_date_to, '') >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("COALESCE(r.test_date_from, '') <= ?")
            params.append(date_to)
        for column, key in (
            ("d.subcontrolarea_name", "subcontrolarea"),
            ("d.substation_name", "substation"),
            ("d.feeder_name", "feeder"),
        ):
            value = _text(filters.get(key))
            if value:
                clauses.append(f"UPPER({column}) LIKE UPPER(?)")
                params.append(f"%{value}%")
        sql = f"""
            SELECT d.*, r.report_no, r.lead, r.testers, r.is_draft,
                   r.created_at, r.updated_at, r.finalized_at, r.test_date_from, r.test_date_to,
                   r.report_uuid
            FROM report_devices d
            JOIN reports r ON r.report_uuid=d.report_uuid
            WHERE {' AND '.join(clauses)}
            ORDER BY UPPER(d.rmu_name),
                     COALESCE(NULLIF(r.finalized_at,''), NULLIF(r.updated_at,''), r.created_at) DESC
        """
        connection = self._connect()
        try:
            rows = [dict(row) for row in connection.execute(sql, params).fetchall()]
        finally:
            connection.close()
        results: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = _text(row.get("display_name") or row.get("rmu_name")).upper()
            if not key:
                continue
            item = results.setdefault(key, {"final": None, "draft": None})
            bucket = "draft" if int(row.get("is_draft") or 0) else "final"
            if item[bucket] is None:
                item[bucket] = row
        return results

    def save_summary_report(
        self,
        summary: Mapping[str, Any],
        html_text: str,
        *,
        software_version: str = "",
        pdf_renderer: Callable[[Path, Path], bool] | None = None,
    ) -> dict[str, Any]:
        if "<html" not in html_text.lower():
            raise ValueError("summary HTML is required")
        summary_uuid = str(uuid.uuid4())
        now = _now_local()
        created_at = now.isoformat(timespec="seconds")
        report_dir = self.summary_reports_dir / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d") / summary_uuid
        report_dir.mkdir(parents=True, exist_ok=False)
        snapshot_path = report_dir / "summary.json"
        html_path = report_dir / "summary.html"
        pdf_path = report_dir / "summary.pdf"
        snapshot = dict(summary)
        snapshot["archive"] = {
            "summary_uuid": summary_uuid,
            "created_at": created_at,
            "software_version": software_version,
        }
        self._write_text_atomic(snapshot_path, json.dumps(snapshot, ensure_ascii=False, indent=2))
        self._write_text_atomic(html_path, html_text)
        pdf_saved = False
        if pdf_renderer is not None:
            try:
                pdf_saved = bool(pdf_renderer(html_path, pdf_path)) and pdf_path.exists() and pdf_path.stat().st_size > 0
            except Exception:
                pdf_saved = False
        if not pdf_saved and pdf_path.exists():
            pdf_path.unlink(missing_ok=True)
        scope = summary.get("scope") if isinstance(summary.get("scope"), Mapping) else {}
        totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
        relative = lambda p: str(p.relative_to(self.application_root)).replace("\\", "/")
        connection = self._connect()
        try:
            connection.execute(
                """
                INSERT INTO summary_reports(
                    summary_uuid, created_at, subcontrolarea, substation, feeder,
                    date_from, date_to, total_devices, tested_devices, passed_devices,
                    failed_devices, completion_rate, pass_rate, software_version,
                    pdf_path, html_path, snapshot_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_uuid, created_at, _text(scope.get("subcontrolarea")),
                    _text(scope.get("substation")), _text(scope.get("feeder")),
                    _text(scope.get("date_from")), _text(scope.get("date_to")),
                    int(totals.get("total") or 0), int(totals.get("tested") or 0),
                    int(totals.get("passed") or 0), int(totals.get("failed") or 0),
                    float(totals.get("completion_rate") or 0), float(totals.get("pass_rate") or 0),
                    software_version, relative(pdf_path) if pdf_saved else "",
                    relative(html_path), relative(snapshot_path),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            shutil.rmtree(report_dir, ignore_errors=True)
            raise
        finally:
            connection.close()
        return {
            "summary_uuid": summary_uuid,
            "created_at": created_at,
            "pdf_saved": pdf_saved,
        }

    def get_summary_report(self, summary_uuid: str) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM summary_reports WHERE summary_uuid=?", (summary_uuid,)).fetchone()
            return dict(row) if row is not None else None
        finally:
            connection.close()

    def resolve_summary_file(self, summary_uuid: str, kind: str) -> Path | None:
        report = self.get_summary_report(summary_uuid)
        if report is None:
            return None
        column = {"pdf": "pdf_path", "html": "html_path", "json": "snapshot_path"}.get(kind)
        if column is None:
            return None
        relative = _text(report.get(column))
        if not relative:
            return None
        path = (self.application_root / relative).resolve()
        try:
            path.relative_to(self.data_root.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def resolve_report_file(self, report_uuid: str, kind: str) -> Path | None:
        report = self.get_report(report_uuid)
        if report is None:
            return None
        column = {"pdf": "pdf_path", "html": "html_path", "json": "snapshot_path"}.get(kind)
        if column is None:
            return None
        relative = _text(report.get(column))
        if not relative:
            return None
        path = (self.application_root / relative).resolve()
        try:
            path.relative_to(self.data_root.resolve())
        except ValueError:
            return None
        return path if path.is_file() else None
