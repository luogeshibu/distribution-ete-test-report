from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import render_report_text
from distribution_signal_verifier.live_report_server import _live_script


def _payload():
    return {
        "network": "distribution",
        "station": "EEH",
        "st_id": "JED-CTL",
        "generated_at": "2026-09-26T20:20:48+03:00",
        "counts": {},
        "points": [],
        "distribution_mappings": [],
        "rmu_names": [],
        "meta_defaults": {"channel": {"protocol": "IEC-104"}},
    }


def test_server_rendered_header_uses_version_before_live_script_runs():
    template = Path("web/distribution_report.html").read_text(encoding="utf-8")
    out = render_report_text(template, _payload(), app_version="1.2.33")
    assert 'hdrSub: (s, id, t) => `配网设备 · 版本 v1.2.33 · 生成 ${t}`' in out
    assert 'hdrSub: (s, id, t) => `Distribution Equipment · Version v1.2.33 · Generated ${t}`' in out
    assert '配网设备 · 变电站 ${s} · 区域 ${id}' not in out
    assert 'Distribution Equipment · Substation ${s} · Area ${id}' not in out


def test_live_script_keeps_same_header_contract():
    js = _live_script("distribution", ["22004"], 60, "IEC-104", "1.2.33")
    assert "配网设备 · 版本 v${appVersion} · 生成 ${t}" in js
    assert "Distribution Equipment · Version v${appVersion} · Generated ${t}" in js
