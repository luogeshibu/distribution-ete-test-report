from distribution_signal_verifier.live_report_server import _live_script


def test_distribution_header_removes_substation_and_area_and_shows_version():
    js = _live_script("distribution", ["22008"], 60, "IEC-104", "1.2.32")
    assert "const appVersion = \"1.2.32\";" in js
    assert "配网设备 · 版本 v${appVersion} · 生成 ${t}" in js
    assert "Distribution Equipment · Version v${appVersion} · Generated ${t}" in js
    assert "变电站 ${s}" not in js
    assert "区域 ${id}" not in js
    assert "Substation ${s}" not in js
    assert "Area ${id}" not in js
