from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, _render_mapping_section, _render_print_mapping_table
from distribution_signal_verifier.live_report_server import _live_script


def sample(name, fid):
    return RmuMapping(combined_id=name, rmu_name=name, adms_gss_fid=fid, rmu_type='2L1T', smart_type='SMART', nop='', function_location='', ip='172.16.11.206', protocol_name='IEC-104')


def test_multi_rmu_selector_appends_without_changing_search_api():
    js = _live_script('distribution', ['22004'], 60, 'IEC-104')
    assert "fetch('/api/rmu-search?q='" in js
    assert "selectedRmus.join(',')" in js
    assert "!selectedRmus.includes(clean)" in js


def test_selected_rmu_table_has_sequence_and_per_device_verdict():
    html = _render_mapping_section([sample('22004','JED-CTL-EEH-AH333-22004'), sample('22005','JED-CTL-EEH-AH333-22005')], ['22004','22005'])
    assert '序号' in html and '总评' in html
    assert 'data-rmu="id:22004"' in html and 'data-rmu="id:22005"' in html
    assert '>1</td>' in html and '>2</td>' in html


def test_pdf_environment_uses_selected_rmu_table():
    html = _render_print_mapping_table([sample('22004','JED-CTL-EEH-AH333-22004')])
    assert 'print-selected-rmu-table' in html
    assert 'FUNCTION LOCATION' in html
    assert 'print-device-verdict' in html
