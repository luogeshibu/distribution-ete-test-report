import json
from pathlib import Path

from distribution_signal_verifier.live_report_server import LiveDataProvider
from distribution_signal_verifier.report_store import ReportStore

ROOT = Path(__file__).resolve().parents[1]
REPORT_HTML = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
HISTORY_HTML = (ROOT / "web" / "history.html").read_text(encoding="utf-8")
SERVER = (ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py").read_text(encoding="utf-8")


def legacy_snapshot():
    return {
        "station": "EEH",
        "lang": "zh",
        "meta": {
            "report_id": "E2E-JED-CTL-EEH-AH333-22004-20260927",
            "station": "EEH",
            "st_id": "JED-CTL",
            "phase": "commission",
            "date_from": "2026-09-27",
            "date_to": "2026-09-27",
            "channel": {
                "protocol": "IEC-104",
                "primary": {"name": "172.16.11.206"},
            },
        },
        "env": {},
        "points": {
            "3800193660570631419:1000": {
                "selected": True,
                "result": "Pass",
                "received": True,
                "note": "legacy",
            }
        },
        "saved_at": "2026-09-27T17:46:15.022Z",
    }


def test_json_is_a_first_class_top_level_menu():
    assert 'data-i18n="btnData"' in REPORT_HTML
    assert 'btnData: "JSON"' in REPORT_HTML
    assert 'btnExportJson: "导出当前 JSON"' in REPORT_HTML
    assert 'btnImportJson: "导入 JSON 到历史"' in REPORT_HTML
    assert 'btnExportJson: "Export Current JSON"' in REPORT_HTML
    assert 'btnImportJson: "Import JSON to History"' in REPORT_HTML


def test_current_json_download_uses_delayed_blob_cleanup():
    assert 'document.body.appendChild(a);' in REPORT_HTML
    assert 'window.setTimeout(() =>' in REPORT_HTML
    assert 'URL.revokeObjectURL(a.href)' in REPORT_HTML


def test_history_has_json_import_entry_point_and_api():
    assert 'id="import-json"' in HISTORY_HTML
    assert 'id="import-json-file"' in HISTORY_HTML
    assert "fetch('/api/reports/import-json'" in HISTORY_HTML
    assert 'parsed.path == "/api/reports/import-json"' in SERVER


def test_legacy_json_recovers_exact_fid_without_oracle():
    provider = object.__new__(LiveDataProvider)
    provider.mappings = lambda selectors: []
    snapshot = provider.normalize_import_snapshot(legacy_snapshot())
    mappings = snapshot["distribution_mappings"]
    assert len(mappings) == 1
    assert mappings[0]["adms_gss_fid"] == "JED-CTL-EEH-AH333-22004"
    assert mappings[0]["rmu_name"] == "22004"
    assert mappings[0]["combined_id"] == "3800193660570631419"
    assert mappings[0]["subcontrolarea_name"] == "JED-CTL"
    assert mappings[0]["substation_name"] == "EEH"
    assert mappings[0]["feeder_name"] == "AH333"


def test_json_import_becomes_sqlite_draft(tmp_path):
    provider = object.__new__(LiveDataProvider)
    provider.mappings = lambda selectors: []
    snapshot = provider.normalize_import_snapshot(legacy_snapshot())
    store = ReportStore(tmp_path)
    result = store.import_json_snapshot(snapshot, software_version="1.2.64")
    assert result["is_draft"] is True
    items = store.list_reports({})
    assert len(items) == 1
    item = items[0]
    assert item["report_no"] == "E2E-JED-CTL-EEH-AH333-22004-20260927"
    assert item["devices"][0]["display_name"] == "JED-CTL-EEH-AH333-22004"
    assert item["html_available"] is False
    assert item["json_available"] is True
    snapshot_path = store.resolve_report_file(result["report_uuid"], "json")
    saved = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert saved["archive"]["source"] == "json_import"
    assert saved["points"]["3800193660570631419:1000"]["result"] == "Pass"


def test_imported_json_history_row_hides_view_pdf_until_resaved():
    assert 'const canView=!!x.html_available' in HISTORY_HTML
    assert 'const viewLink=canView?' in HISTORY_HTML
    assert 'const htmlLink=canView?' in HISTORY_HTML
