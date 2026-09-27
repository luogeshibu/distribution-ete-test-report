import json
from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import build_smart_inventory_sql
from distribution_signal_verifier.live_report_server import LiveDataProvider, OracleSettings
from distribution_signal_verifier.report_store import ReportStore, SCHEMA_VERSION


def _final_payload(rmu='22008', station='ABS', feeder='AH321', verdict='pass'):
    return {
        'snapshot': {
            'network': 'distribution',
            'meta': {
                'report_id': f'E2E-{rmu}',
                'date_from': '2026-09-26',
                'date_to': '2026-09-26',
                'phase': 'commission',
                'lead': 'Team Lead',
                'testers': 'Team 1',
                'adms_version': 'ADMS-X',
                'device_verdicts': {rmu: verdict},
            },
            'distribution_mappings': [{
                'rmu_name': rmu,
                'adms_gss_fid': f'JED-NTH-{station}-{feeder}-{rmu}',
                'rmu_type': '2L1T',
                'smart_type': 'SMART',
                'nop': '',
                'function_location': 'FL-1',
                'feeder_name': feeder,
                'substation_name': station,
                'subcontrolarea_name': 'JED-NTH',
            }],
            'points_full': [],
        },
        'html': '<!doctype html><html><body>ETE</body></html>',
        'is_draft': False,
    }


def test_smart_inventory_sql_is_separate_and_scope_bound():
    sql, binds = build_smart_inventory_sql('ABS', 'AH321', 'JED-NTH')
    assert 'd5000.dms_combined_device' in sql
    assert 'comb.combined_type BETWEEN 21 AND 25' in sql
    assert 'comb.combined_type BETWEEN 41 AND 45' in sql
    assert 'comb.combined_type BETWEEN 61 AND 63' in sql
    assert binds['substation'] == 'ABS'
    assert binds['feeder'] == 'AH321'
    assert binds['subcontrolarea'] == 'JED-NTH'


def test_v3_inventory_cache_and_latest_final_result_survive_reopen(tmp_path):
    store = ReportStore(tmp_path)
    assert SCHEMA_VERSION == 3
    store.upsert_inventory([{
        'combined_id': 1, 'rmu_name': '22008', 'display_name': 'JED-NTH-ABS-AH321-22008',
        'rmu_type': '2L1T', 'smart_type': 'SMART', 'feeder_name': 'AH321',
        'substation_name': 'ABS', 'subcontrolarea_name': 'JED-NTH',
    }])
    store.save_report(_final_payload(), software_version='1.2.31')
    reopened = ReportStore(tmp_path)
    inv = reopened.list_inventory({'substation': 'ABS', 'feeder': 'AH321'})
    assert len(inv) == 1
    latest = reopened.latest_device_results({'substation': 'ABS', 'feeder': 'AH321'})
    assert latest['JED-NTH-ABS-AH321-22008']['final']['verdict'] == 'pass'


def test_dashboard_summary_merges_inventory_and_latest_test_state(tmp_path):
    mapping_path = tmp_path / 'mapping.json'
    mapping_path.write_text(json.dumps([
        {'COMBINED_ID': 1, 'RMU_NAME': '22008', 'ADMS_GSS_FID': 'JED-NTH-ABS-AH321-22008', 'RMU_TYPE': '2L1T', 'SMART_TYPE': 'SMART', 'FEEDER_NAME': 'AH321', 'SUBSTATION_NAME': 'ABS', 'SUBCONTROLAREA_NAME': 'JED-NTH'},
        {'COMBINED_ID': 2, 'RMU_NAME': '22009', 'ADMS_GSS_FID': 'JED-NTH-ABS-AH321-22009', 'RMU_TYPE': '2L1T', 'SMART_TYPE': 'SMART', 'FEEDER_NAME': 'AH321', 'SUBSTATION_NAME': 'ABS', 'SUBCONTROLAREA_NAME': 'JED-NTH'},
        {'COMBINED_ID': 3, 'RMU_NAME': '22010', 'ADMS_GSS_FID': 'JED-NTH-ABS-AH321-22010', 'RMU_TYPE': '2L1T', 'SMART_TYPE': 'NONSMART', 'FEEDER_NAME': 'AH321', 'SUBSTATION_NAME': 'ABS', 'SUBCONTROLAREA_NAME': 'JED-NTH'},
    ]), encoding='utf-8')
    store = ReportStore(tmp_path)
    store.save_report(_final_payload('22008'), software_version='1.2.31')
    provider = object.__new__(LiveDataProvider)
    provider.config = type('Cfg', (), {'mapping_json': mapping_path})()
    provider.report_store = store
    provider.oracle = OracleSettings()
    summary = provider.dashboard_summary({'substation': 'ABS', 'feeder': 'AH321'})
    assert summary['totals']['total'] == 2
    assert summary['totals']['tested'] == 1
    assert summary['totals']['passed'] == 1
    assert summary['totals']['untested'] == 1
    assert summary['totals']['completion_rate'] == 50.0
    assert summary['totals']['pass_rate'] == 100.0
    assert len(summary['feeders']) == 1


def test_summary_report_is_persisted_under_program_data(tmp_path):
    store = ReportStore(tmp_path)
    summary = {
        'scope': {'subcontrolarea': 'JED-NTH', 'substation': 'ABS', 'feeder': 'AH321', 'date_from': '', 'date_to': ''},
        'totals': {'total': 2, 'tested': 1, 'passed': 1, 'failed': 0, 'completion_rate': 50.0, 'pass_rate': 100.0},
        'devices': [], 'feeders': [],
    }
    saved = store.save_summary_report(summary, '<!doctype html><html><body>Summary</body></html>', software_version='1.2.31')
    assert store.resolve_summary_file(saved['summary_uuid'], 'html').is_file()
    assert store.resolve_summary_file(saved['summary_uuid'], 'json').is_file()
    assert str(store.resolve_summary_file(saved['summary_uuid'], 'html')).startswith(str(tmp_path / 'data' / 'summary_reports'))


def test_dashboard_ui_and_routes_are_wired():
    dashboard = Path('web/dashboard.html').read_text(encoding='utf-8')
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    server = Path('src/distribution_signal_verifier/live_report_server.py').read_text(encoding='utf-8')
    build = Path('scripts/build_release.ps1').read_text(encoding='utf-8')
    assert '智能设备总数' in dashboard
    assert '导出总体报表' in dashboard
    assert '/api/dashboard?' in dashboard
    assert '/api/dashboard/export' in dashboard
    assert 'id="btn-dashboard"' in report
    assert 'parsed.path == "/dashboard"' in server
    assert 'parsed.path == "/api/dashboard"' in server
    assert 'parsed.path == "/api/dashboard/export"' in server
    assert 'web\\dashboard.html' in build
    assert 'data\\summary_reports' in build
