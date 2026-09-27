from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import _render_mapping_section


def test_static_report_uses_distribution_device_search_title():
    report = Path("web/distribution_report.html").read_text(encoding="utf-8")
    assert "1. 配网设备查询" in report
    assert "1. Distribution Device Search" in report
    assert "1. 配网环网柜查询" not in report


def test_server_rendered_report_uses_distribution_device_search_title():
    html = _render_mapping_section([])
    assert "1. 配网设备查询" in html
    assert "1. Distribution Device Search" in html
    assert "1. 配网环网柜查询" not in html


def test_rmu_input_label_and_search_scope_are_unchanged():
    html = _render_mapping_section([])
    assert "环网柜名称（RMU Name）" in html
    assert "RMU Name" in html
