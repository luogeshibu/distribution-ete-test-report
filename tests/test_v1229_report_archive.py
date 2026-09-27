import json
from pathlib import Path

from distribution_signal_verifier.report_store import ReportStore


def _payload(html='<!doctype html><html><body>ETE</body></html>'):
    return {
        'snapshot': {
            'network': 'distribution',
            'meta': {
                'report_id': 'E2E-JED-CTL-EEH-AH333-22004-20260926',
                'date_from': '2026-09-26',
                'date_to': '2026-09-26',
                'phase': 'commission',
                'lead': 'Tester A',
                'testers': 'Team 1',
                'adms_version': 'ADMS-X',
                'device_verdicts': {'22004': 'pass'},
            },
            'distribution_mappings': [
                {
                    'rmu_name': '22004',
                    'adms_gss_fid': 'JED-CTL-EEH-AH333-22004',
                    'rmu_type': '2L1T',
                    'smart_type': 'SMART',
                    'nop': '',
                    'function_location': 'FL-001',
                    'ip': '172.16.1.10',
                    'protocol_name': 'IEC-104',
                    'feeder_name': 'AH333',
                    'substation_name': 'EEH',
                    'subcontrolarea_name': 'JED-CTL',
                }
            ],
            'points_full': [],
        },
        'html': html,
        'is_draft': False,
    }


def test_report_store_is_inside_application_root_and_persists(tmp_path):
    store = ReportStore(tmp_path)
    assert store.db_path == tmp_path / 'data' / 'database' / 'ete_reports.db'
    saved = store.save_report(_payload(), client_ip='10.0.0.5', software_version='1.2.29')
    assert saved['device_count'] == 1
    assert store.resolve_report_file(saved['report_uuid'], 'html').is_file()
    assert store.resolve_report_file(saved['report_uuid'], 'json').is_file()

    # Re-opening the store simulates a software restart/upgrade and must keep history.
    reopened = ReportStore(tmp_path)
    rows = reopened.list_reports({'device': '22004'})
    assert len(rows) == 1
    assert rows[0]['software_version'] == '1.2.29'
    assert rows[0]['devices'][0]['substation_name'] == 'EEH'
    assert rows[0]['devices'][0]['feeder_name'] == 'AH333'
    assert rows[0]['verdict_summary'] == 'pass'


def test_archive_snapshot_keeps_device_hierarchy(tmp_path):
    store = ReportStore(tmp_path)
    saved = store.save_report(_payload(), software_version='1.2.29')
    snapshot = json.loads(store.resolve_report_file(saved['report_uuid'], 'json').read_text(encoding='utf-8'))
    mapping = snapshot['distribution_mappings'][0]
    assert mapping['subcontrolarea_name'] == 'JED-CTL'
    assert mapping['substation_name'] == 'EEH'
    assert mapping['feeder_name'] == 'AH333'
    assert snapshot['archive']['software_version'] == '1.2.29'


def test_history_template_and_print_archive_flow_exist():
    history = Path('web/history.html').read_text(encoding='utf-8')
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    server = Path('src/distribution_signal_verifier/live_report_server.py').read_text(encoding='utf-8')
    assert '/api/reports?' in history
    assert '下载 PDF' in history and '下载 JSON' in history
    assert 'id="btn-history"' in report
    assert 'async function archiveCurrentReport(isDraft)' in report
    assert 'await archiveCurrentReport(false);' in report
    assert 'frozenPrintHtml()' in report
    assert 'parsed.path == "/history"' in server
    assert 'parsed.path == "/api/reports"' in server


def test_release_build_bundles_history_and_preserves_data_directory_contract():
    text = Path('scripts/build_release.ps1').read_text(encoding='utf-8')
    assert 'web\\history.html' in text
    assert 'distribution-ete-test-report-v$version' in text
    assert 'data\\database' in text
    assert 'data\\reports' in text
    assert 'data\\backup\\database' in text


def test_report_store_supports_five_concurrent_archive_writers(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    store = ReportStore(tmp_path)

    def save(index):
        payload = _payload()
        payload['snapshot']['meta']['report_id'] = f'R-{index}'
        payload['snapshot']['meta']['lead'] = f'Lead-{index}'
        payload['snapshot']['distribution_mappings'][0]['rmu_name'] = f'RMU-{index}'
        payload['snapshot']['distribution_mappings'][0]['adms_gss_fid'] = f'JAZ-SUB-F01-RMU-{index}'
        payload['snapshot']['meta']['device_verdicts'] = {f'RMU-{index}': 'pass'}
        return store.save_report(payload, software_version='1.2.29')

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(save, range(10)))

    assert len(results) == 10
    assert len(store.list_reports({})) == 10
