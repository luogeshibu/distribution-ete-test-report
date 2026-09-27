from pathlib import Path

from distribution_signal_verifier.live_report_server import LiveDataProvider, OracleSettings
from distribution_signal_verifier.report_store import ReportStore


def _payload(*, rmu='22008', station='ABS', feeder='AH321', verdict='pass', is_draft=False):
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
                'device_verdicts': {rmu: verdict} if verdict else {},
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
        'is_draft': is_draft,
    }


def _provider(tmp_path):
    provider = object.__new__(LiveDataProvider)
    provider.config = type('Cfg', (), {'mapping_json': None})()
    provider.report_store = ReportStore(tmp_path)
    # Configure a nominal Oracle connection to prove that no-scope mode still
    # does not attempt an inventory query.
    provider.oracle = OracleSettings(host='db', service='svc', username='u', password='p')
    return provider


def test_dashboard_without_scope_uses_local_history_and_never_queries_oracle(tmp_path):
    provider = _provider(tmp_path)
    provider.report_store.save_report(_payload(), software_version='1.2.38')

    def forbidden_inventory(_filters):
        raise AssertionError('no-scope history dashboard must not query Oracle/inventory')

    provider._dashboard_inventory = forbidden_inventory
    summary = provider.dashboard_summary({})

    assert summary['mode'] == 'history'
    assert summary['coverage_available'] is False
    assert summary['inventory_source'] == 'history'
    assert summary['totals']['total'] == 1
    assert summary['totals']['tested'] == 1
    assert summary['totals']['passed'] == 1
    assert summary['totals']['untested'] is None
    assert summary['totals']['completion_rate'] is None
    assert summary['totals']['pass_rate'] == 100.0
    assert summary['devices'][0]['display_name'] == 'JED-NTH-ABS-AH321-22008'
    assert summary['devices'][0]['status'] == 'tested'


def test_dashboard_date_only_filter_stays_local_history_mode(tmp_path):
    provider = _provider(tmp_path)
    provider.report_store.save_report(_payload(), software_version='1.2.38')
    provider._dashboard_inventory = lambda _filters: (_ for _ in ()).throw(
        AssertionError('date-only dashboard must not query Oracle/inventory')
    )

    summary = provider.dashboard_summary({'date_from': '2026-09-01', 'date_to': '2026-09-30'})
    assert summary['mode'] == 'history'
    assert summary['totals']['total'] == 1


def test_dashboard_with_network_scope_keeps_coverage_inventory_behavior(tmp_path):
    provider = _provider(tmp_path)
    provider.report_store.save_report(_payload(), software_version='1.2.38')
    calls = []

    def scoped_inventory(filters):
        calls.append(dict(filters))
        return ([
            {
                'combined_id': 1,
                'rmu_name': '22008',
                'display_name': 'JED-NTH-ABS-AH321-22008',
                'rmu_type': '2L1T', 'smart_type': 'SMART',
                'feeder_name': 'AH321', 'substation_name': 'ABS', 'subcontrolarea_name': 'JED-NTH',
            },
            {
                'combined_id': 2,
                'rmu_name': '22009',
                'display_name': 'JED-NTH-ABS-AH321-22009',
                'rmu_type': '2L1T', 'smart_type': 'SMART',
                'feeder_name': 'AH321', 'substation_name': 'ABS', 'subcontrolarea_name': 'JED-NTH',
            },
        ], 'oracle', '2026-09-27T08:00:00+03:00', '')

    provider._dashboard_inventory = scoped_inventory
    summary = provider.dashboard_summary({'substation': 'ABS', 'feeder': 'AH321'})

    assert len(calls) == 1
    assert summary['mode'] == 'coverage'
    assert summary['coverage_available'] is True
    assert summary['totals']['total'] == 2
    assert summary['totals']['tested'] == 1
    assert summary['totals']['untested'] == 1
    assert summary['totals']['completion_rate'] == 50.0
    assert summary['totals']['pass_rate'] == 100.0


def test_dashboard_ui_auto_loads_history_and_does_not_require_scope():
    dashboard = Path('web/dashboard.html').read_text(encoding='utf-8')
    assert '历史测试总览（未查询 Oracle）' in dashboard
    assert '页面打开时先展示服务端本地历史 ETE 报告，不查询 Oracle' in dashboard
    assert "alert('请至少输入区域、变电站或馈线中的一项。')" not in dashboard
    assert '\nload();\n</script>' in dashboard
    assert "sourceLabel(d.inventory_source)" in dashboard
