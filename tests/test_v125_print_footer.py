from pathlib import Path

HTML = (Path(__file__).parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")


def test_print_footer_is_centered_page_number_only():
    assert "@bottom-center" in HTML
    assert 'content: counter(page) " / " counter(pages);' in HTML
    assert "@bottom-left" not in HTML
    assert "@bottom-right" not in HTML
    assert 'content: "Page " counter(page)' not in HTML


def test_print_footer_no_generated_datetime():
    assert 'const printTime =' not in HTML
    assert 'footerTime.textContent = printTime' not in HTML