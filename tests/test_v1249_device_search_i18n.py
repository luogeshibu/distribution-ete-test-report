from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import (
    RmuMapping,
    _render_mapping_section,
    _render_print_mapping_table,
)
from distribution_signal_verifier.live_report_server import _live_script


def _mapping():
    return [RmuMapping(combined_id="1", rmu_name="22004", adms_gss_fid="JED-CTL-EEH-AH333-22004", rmu_type="2L1T", smart_type="SMART")]


def test_device_search_area_uses_device_wording_in_both_languages():
    html = _render_mapping_section(_mapping(), ["fid:JED-CTL-EEH-AH333-22004"])
    assert 'data-live-zh="">设备名称</span>' in html
    assert 'data-live-en="" style="display:none">Device Name</span>' in html
    assert ">Device Name<" in html
    assert ">设备类型<" in html
    assert ">Device Type<" in html
    assert "追加设备" in html
    assert "add devices" in html


def test_empty_device_search_uses_device_wording():
    html = _render_mapping_section([], ["fid:missing"])
    assert "未查询到匹配的设备" in html
    assert "No matching device was found" in html


def test_overall_result_options_have_bilingual_labels():
    html = _render_mapping_section(_mapping(), ["fid:JED-CTL-EEH-AH333-22004"])
    assert 'data-label-zh="（未选）" data-label-en="(Not selected)"' in html
    assert 'data-label-zh="通过" data-label-en="Pass"' in html
    assert 'data-label-zh="不通过" data-label-en="Fail"' in html
    js = _live_script("distribution", ["fid:JED-CTL-EEH-AH333-22004"], 60, "IEC-104", "1.2.49")
    assert "option.dataset.labelEn" in js
    assert "option.dataset.labelZh" in js


def test_print_mapping_table_uses_device_headers():
    html = _render_print_mapping_table(_mapping())
    assert ">设备名称<" in html
    assert ">Device Name<" in html
    assert ">设备类型<" in html
    assert ">Device Type<" in html


def test_live_search_messages_and_placeholder_are_device_scoped():
    js = _live_script("distribution", [], 60, "IEC-104", "1.2.49")
    assert "No matching device found" in js
    assert "未查询到匹配的设备" in js
    assert "Device search failed" in js
    assert "设备搜索失败" in js
    assert "e.g. enter a device name or number and select a device" in js
    assert "例如：输入设备名称或编号后选择设备" in js


def test_static_template_device_label_is_updated():
    text = Path("web/distribution_report.html").read_text(encoding="utf-8")
    assert '<span data-live-zh="">设备名称</span>' in text
    assert '<span data-live-en="" style="display:none">Device Name</span>' in text
    assert ">Device Name<" in text
