from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")


def test_json_menu_uses_same_header_action_box():
    assert ".app-bar .actions > button" in HTML
    assert ".app-bar .actions > .data-menu > #btn-data-menu" in HTML
    assert "min-width: 5rem" in HTML
    assert "min-height: 2rem" in HTML
    assert "height: 2rem" in HTML
    assert "display: inline-flex" in HTML
    assert "align-items: center" in HTML
    assert "justify-content: center" in HTML


def test_version_is_1265():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.2.71"
