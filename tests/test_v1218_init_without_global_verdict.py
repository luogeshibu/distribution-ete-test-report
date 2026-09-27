from pathlib import Path


def test_removed_report_verdict_does_not_abort_browser_init():
    html = (Path(__file__).resolve().parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")
    assert 'id="meta-verdict"' not in html
    assert 'if (verdict) {' in html
    assert 'verdict.innerHTML = "";' in html
    assert 'renderDistributionChannels();' in html
    assert "3.' + group.index" in html
    assert '"4." + group.index' in html


def test_multi_rmu_sections_still_use_payload_metadata():
    html = (Path(__file__).resolve().parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")
    assert 'RAW.distribution_mappings' in html
    assert 'pointRmuIdentity(p) === group.key' in html
