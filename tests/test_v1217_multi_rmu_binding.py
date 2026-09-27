from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = (ROOT / "src/distribution_signal_verifier/live_report_server.py").read_text(encoding="utf-8")
HTML = (ROOT / "web/distribution_report.html").read_text(encoding="utf-8")

def test_rows_are_stamped_with_rmu_identity_without_sql_change():
    assert 'tagged["RMU_NAME"] = item.rmu_name' in SERVER
    assert 'tagged["RMU_DISPLAY_NAME"] = item.adms_gss_fid or item.rmu_name' in SERVER

def test_section_two_lists_all_selected_rmus():
    assert 'id="multi-rmu-channel-list"' in HTML
    assert 'function renderDistributionChannels()' in HTML
    assert "mappings.map((m, i)" in HTML
    assert "m.protocol_name || 'IEC-104'" in HTML
    assert "m.ip || ''" in HTML
