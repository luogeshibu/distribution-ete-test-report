from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from distribution_signal_verifier.distribution_signal_verifier import build_rmu_search_sql
from distribution_signal_verifier.live_report_server import LiveDataProvider


def test_346_sql_is_substring_search_and_keeps_user_relationships():
    sql, binds = build_rmu_search_sql('346', 50)
    assert binds == {'rmu_keyword': '346'}
    assert 'INSTR(UPPER(TRIM(comb.name)), q.keyword) > 0' in sql
    assert 'LEFT JOIN d5000.dms_feeder_device feeder ON feeder.id = comb.feeder_id' in sql
    assert 'LEFT JOIN d5000.substation sub ON sub.id = feeder.st_id' in sql
    assert 'LEFT JOIN d5000.subcontrolarea sca ON sca.id = sub.subarea_id' in sql
    assert 'ROWNUM <= 50' in sql


def test_search_rmus_returns_selectable_candidates_without_loading_points():
    provider = object.__new__(LiveDataProvider)
    provider.config = type('Cfg', (), {'mapping_json': None})()
    provider.oracle = type('OracleCfg', (), {'configured': True})()
    calls = []
    def fake_execute(sql, binds):
        calls.append((sql, binds))
        return [
            {'COMBINED_ID': 1, 'RMU_NAME': '34661', 'ADMS_GSS_FID': 'JED-NTH-ABH-AH303-34661', 'RMU_TYPE':'2L1T','SMART_TYPE':'SMART','NOP':'NOP'},
            {'COMBINED_ID': 2, 'RMU_NAME': 'OLD_34688', 'ADMS_GSS_FID': 'JED-NTH-ABH-AH304-OLD_34688', 'RMU_TYPE':'3L1T','SMART_TYPE':'NONSMART','NOP':''},
        ]
    provider._execute_rows = fake_execute
    items = provider.search_rmus('346')
    assert [x['rmu_name'] for x in items] == ['34661', 'OLD_34688']
    assert items[0]['adms_gss_fid'].endswith('34661')
    assert calls[0][1] == {'rmu_keyword':'346'}


def test_runtime_script_searches_then_selects():
    from distribution_signal_verifier.live_report_server import _live_script
    js = _live_script('distribution', [], 60, 'IEC-104')
    assert "/api/rmu-search?q=" in js
    assert "renderSuggestions(items)" in js
    assert "selectionToken(item)" in js
    assert "openRmu(selectedSelector)" in js
    assert "环网柜搜索失败" in js
