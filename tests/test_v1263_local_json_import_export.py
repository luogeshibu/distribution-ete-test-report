from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")


def test_json_tools_are_grouped_under_data_menu():
    assert 'id="btn-data-menu"' in HTML
    assert 'data-i18n="btnData"' in HTML
    assert 'id="btn-export-json"' in HTML
    assert 'id="btn-import-json"' in HTML
    assert 'id="json-import-input"' in HTML
    assert 'accept=".json,application/json"' in HTML


def test_json_tools_are_bilingual():
    assert 'btnData: "JSON"' in HTML
    assert 'btnExportJson: "导出当前 JSON"' in HTML
    assert 'btnImportJson: "导入 JSON 到历史"' in HTML
    assert 'btnData: "JSON"' in HTML
    assert 'btnExportJson: "Export Current JSON"' in HTML
    assert 'btnImportJson: "Import JSON to History"' in HTML


def test_local_json_export_uses_self_contained_archive_snapshot():
    assert 'const snapshot = archiveSnapshot();' in HTML
    assert 'schema: "distribution-ete-test-report"' in HTML
    assert 'snapshot.local_json' in HTML


def test_local_json_import_restores_exact_selected_devices():
    assert 'function importedDeviceSelector(mapping)' in HTML
    assert 'return "fid:" + display;' in HTML
    assert 'params.set("rmu", selectors.join(","));' in HTML
    assert 'params.set("handoff", token);' in HTML
    assert 'report_uuid: ""' in HTML


def test_legacy_json_still_loads_on_current_devices():
    assert 'Legacy JSON did not contain device mappings' in HTML
    assert 'applyLoaded(snapshot);' in HTML
    assert 'rememberReportUuid("", false);' in HTML


def test_json_import_does_not_control_language():
    start = HTML.index('function prepareImportedJsonHandoff(snapshot)')
    end = HTML.index('function refreshAfterLocalJsonLoad()', start)
    block = HTML[start:end]
    assert 'lang' not in block.lower()
