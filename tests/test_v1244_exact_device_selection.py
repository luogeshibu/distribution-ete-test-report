from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import (
    RmuMapping,
    _render_mapping_section,
    _render_print_mapping_table,
    build_rmu_id_sql,
)
from distribution_signal_verifier.live_report_server import _live_script


def test_exact_selected_device_query_uses_combined_id_only():
    sql, binds = build_rmu_id_sql([101, 202])
    assert 'JOIN d5000.dms_combined_device comb' in sql
    assert 'TO_CHAR(comb.id) = TRIM(l.combined_id)' in sql
    assert 'REGEXP_LIKE' not in sql
    assert binds == {'combined_id_0': '101', 'combined_id_1': '202'}


def test_search_api_candidate_contains_combined_id(tmp_path):
    # Static helper contract: browser needs the unique DB identity, not only the
    # short RMU name which may be duplicated on different feeders.
    server = Path(__file__).resolve().parents[1] / 'src' / 'distribution_signal_verifier' / 'live_report_server.py'
    text = server.read_text(encoding='utf-8')
    assert '"combined_id": m.combined_id' in text


def test_clicking_suggestion_adds_exact_selection_token():
    js = _live_script('distribution', [], 60, 'IEC-104', '1.2.44')
    assert "return 'id:' + String(combinedId).trim();" in js
    assert 'selectedSelector = selectionToken(item);' in js
    assert 'openRmu(selectedSelector);' in js
    assert 'openRmu(item.rmu_name);' not in js


def test_remove_button_is_bound_to_exact_device_identity():
    mapping = [
        RmuMapping(combined_id=101, rmu_name='6', adms_gss_fid='JED-CTL-ADF-AH315-6'),
        RmuMapping(combined_id=202, rmu_name='6', adms_gss_fid='JED-CTL-ANS-AH325-6'),
    ]
    html = _render_mapping_section(mapping, ['id:101', 'id:202'])
    assert 'data-rmu="id:101"' in html
    assert 'data-rmu="id:202"' in html
    assert html.count('JED-CTL-ADF-AH315-6') == 1
    assert html.count('JED-CTL-ANS-AH325-6') == 1


def test_print_verdict_keys_are_unique_for_duplicate_short_names():
    mapping = [
        RmuMapping(combined_id=101, rmu_name='6', adms_gss_fid='JED-CTL-ADF-AH315-6'),
        RmuMapping(combined_id=202, rmu_name='6', adms_gss_fid='JED-CTL-ANS-AH325-6'),
    ]
    html = _render_print_mapping_table(mapping)
    assert 'data-rmu="id:101"' in html
    assert 'data-rmu="id:202"' in html


def test_report_groups_points_by_combined_id_not_duplicate_rmu_name():
    html = (Path(__file__).resolve().parents[1] / 'web' / 'distribution_report.html').read_text(encoding='utf-8')
    assert 'function rmuIdentity(m)' in html
    assert 'function pointRmuIdentity(p)' in html
    assert "return 'id:' + String(m.combined_id).trim();" in html
    assert 'pointRmuIdentity(p) === group.key' in html
