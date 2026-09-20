from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from distribution_signal_verifier.distribution_signal_verifier import build_rmu_sql, build_rmu_search_sql
from distribution_signal_verifier.live_report_server import LiveDataProvider, _live_script


def test_exact_rmu_name_with_letters_and_hyphen_is_bound_as_text():
    sql, binds = build_rmu_sql(['F05-1509'])
    assert binds == {'rmu_0': 'F05-1509'}
    assert 'TRIM(comb.name) = TRIM(r.rmu_name)' in sql


def test_partial_search_supports_each_part_of_alphanumeric_hyphen_name():
    for keyword in ('F05', '1509', 'F05-1509'):
        sql, binds = build_rmu_search_sql(keyword)
        assert binds == {'rmu_keyword': keyword}
        assert 'INSTR(UPPER(TRIM(comb.name)), q.keyword) > 0' in sql


def test_provider_returns_f05_1509_as_string_candidate():
    provider = object.__new__(LiveDataProvider)
    provider.config = type('Cfg', (), {'mapping_json': None})()
    provider.oracle = type('OracleCfg', (), {'configured': True})()
    provider._execute_rows = lambda sql, binds: [
        {'COMBINED_ID': 15, 'RMU_NAME': 'F05-1509', 'ADMS_GSS_FID': 'JED-SUB-F05-F05-1509',
         'RMU_TYPE': '2L1T', 'SMART_TYPE': 'SMART', 'NOP': ''}
    ]
    items = provider.search_rmus('F05')
    assert items[0]['rmu_name'] == 'F05-1509'


def test_browser_selection_url_encodes_alphanumeric_rmu_name():
    js = _live_script('distribution', [], 60, 'IEC-104')
    assert "params.set('rmu', name)" in js
    assert "new URLSearchParams()" in js
    assert 'openRmu(item.rmu_name)' in js