from pathlib import Path

from distribution_signal_verifier.live_report_server import _live_script


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py"


def test_live_test_page_has_no_periodic_full_page_reload():
    text = SERVER.read_text(encoding="utf-8")
    assert "window.location.reload()" not in text
    js = _live_script("distribution", ["22004"], 60, "IEC-104", "1.2.43")
    assert "window.location.reload()" not in js


def test_version_is_1243():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.2.44"
