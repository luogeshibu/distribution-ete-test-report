from pathlib import Path


def test_home_precedes_language_switcher_and_reset():
    html = (Path(__file__).resolve().parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")
    i_home = html.index('id="btn-home"')
    i_zh = html.index('id="lang-zh"')
    i_en = html.index('id="lang-en"')
    i_reset = html.index('id="btn-reset-current"')
    assert i_home < i_zh < i_en < i_reset
