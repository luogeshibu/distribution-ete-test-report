from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, _render_print_mapping_table


def test_print_rmu_table_has_dedicated_colgroup():
    html = _render_print_mapping_table([
        RmuMapping(
            rmu_name="JED-CTL-EEH-AH333-22004",
            adms_gss_fid="JED-CTL-EEH-AH333-22004",
            rmu_type="2L1T",
            smart_type="SMART",
            nop="",
            function_location="",
            ip="172.16.11.206",
            protocol_name="IEC-104",
        )
    ])
    assert 'class="points print-rmu-table"' in html
    assert '<col class="col-rmu">' in html
    assert '<col class="col-location">' in html
    assert '<col class="col-ip">' in html
    assert '<col class="col-verdict">' in html


def test_print_css_has_rmu_specific_widths_and_cover_omits_channel_summary():
    template = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert '#print-selected-rmu-table col.col-rmu' in template
    assert '#print-selected-rmu-table col.col-location' in template
    assert '#print-selected-rmu-table col.col-ip' in template
    update_meta = template.split('function updatePrintMeta()', 1)[1].split('function renderEnv()', 1)[0]
    assert '[t("printChannels"), channelPrintSummary()]' not in update_meta
