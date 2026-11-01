from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import (
    RmuMapping,
    _mapping_selector,
    build_rmu_fid_sql,
)
from distribution_signal_verifier.live_report_server import _live_script


def test_mouse_selection_prefers_full_displayed_fid():
    js = _live_script('distribution', [], 60, 'IEC-104', '1.2.45')
    fid_pos = js.index("if (fid) return 'fid:' + fid;")
    id_pos = js.index("return 'id:' + String(combinedId).trim();")
    assert fid_pos < id_pos
    assert 'openRmu(selectedSelector);' in js
    assert 'openRmu(item.rmu_name);' not in js


def test_exact_fid_query_uses_full_clicked_display_name():
    sql, binds = build_rmu_fid_sql([
        'JED-CTL-ANS-AH325-6',
        'JED-CTL-EEH-AH333-22004',
    ])
    assert "UPPER(TRIM(sca.name || '-' || sub.name || '-' || feeder.name || '-' || comb.name))" in sql
    assert '= UPPER(TRIM(l.adms_gss_fid))' in sql
    assert 'REGEXP_LIKE' not in sql
    assert binds == {
        'adms_gss_fid_0': 'JED-CTL-ANS-AH325-6',
        'adms_gss_fid_1': 'JED-CTL-EEH-AH333-22004',
    }


def test_browser_selector_is_full_fid_even_when_final_number_is_duplicated():
    item = RmuMapping(
        combined_id=12345678901234567890,
        rmu_name='6',
        adms_gss_fid='JED-CTL-ANS-AH325-6',
    )
    assert _mapping_selector(item) == 'fid:JED-CTL-ANS-AH325-6'


def test_search_api_serializes_combined_id_as_string():
    server = Path(__file__).resolve().parents[1] / 'src' / 'distribution_signal_verifier' / 'live_report_server.py'
    text = server.read_text(encoding='utf-8')
    assert '"combined_id": "" if m.combined_id in (None, "") else str(m.combined_id)' in text


def test_old_id_selector_is_kept_as_remove_and_verdict_alias():
    core = (Path(__file__).resolve().parents[1] / 'src' / 'distribution_signal_verifier' / 'distribution_signal_verifier.py').read_text(encoding='utf-8')
    server = (Path(__file__).resolve().parents[1] / 'src' / 'distribution_signal_verifier' / 'live_report_server.py').read_text(encoding='utf-8')
    assert 'data-rmu-id=' in core
    assert 'button.dataset.rmuId' in server
    assert 'sel.dataset.rmuId' in server
