from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, _render_mapping_section
from distribution_signal_verifier.live_report_server import _live_script

ROOT = Path(__file__).resolve().parents[1]


def _html() -> str:
    return (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")


def test_selected_rmu_table_has_per_row_remove_button():
    mapping = [RmuMapping(combined_id=1001, rmu_name="JED-TEST-001", adms_gss_fid="JED-TEST-001")]
    html = _render_mapping_section(mapping, ["JED-TEST-001"])
    assert "操作" in html
    assert "Action" in html
    assert 'class="rmu-remove-button compact"' in html
    assert 'data-rmu="fid:JED-TEST-001"' in html
    assert 'data-rmu-id="id:1001"' in html
    assert "移除" in html


def test_live_script_removes_only_selected_rmu_and_reloads_remaining_list():
    js = _live_script("distribution", ["JED-TEST-001", "JED-TEST-002"], 60, "IEC-104")
    assert "function removeRmu(name, idAlias)" in js
    assert "selectedRmus.splice(index, 1)" in js
    assert "navigateSelectedRmus();" in js
    assert "document.querySelectorAll('.rmu-remove-button[data-rmu]')" in js


def test_cover_hides_report_id_station_and_area_fields():
    html = _html()
    assert 'id="meta-report_id"' not in html
    assert 'id="meta-station"' not in html
    assert 'id="meta-st_id"' not in html
    # They also no longer appear on the printed cover metadata.
    print_meta = html.split('function updatePrintMeta()', 1)[1].split('const signMeta', 1)[0]
    assert 'printReportId' not in print_meta
    assert 'printStation' not in print_meta
    assert 'printStId' not in print_meta


def test_environment_section_is_removed_from_screen_but_retained_for_print_mapping_table():
    html = _html()
    assert '<section class="card print-only" id="env">' in html
    assert '<span class="screen-section-no">3. </span><span class="print-section-no">2. </span>' in html
    assert '<span class="screen-section-no">4. </span><span data-i18n="secPoints">' in html
    assert '<span class="screen-section-no">5. </span><span class="print-section-no">4. </span>' in html
    assert "<h3>3.' + group.index" in html
    assert 'title.textContent = "4." + group.index' in html
