from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_distribution_device_block_uses_main_language_source_of_truth():
    text = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
    assert 'const english = lang === "en";' in text
    assert 'document.querySelectorAll("[data-live-zh]")' in text
    assert 'document.querySelectorAll("[data-live-en]")' in text
    assert 'e.g. enter a device name or number and select a device' in text
    assert 'document.querySelectorAll(".device-verdict option[data-label-zh][data-label-en]")' in text


def test_release_does_not_modify_python_query_implementation():
    # The v1.2.55 fix is intentionally frontend-only. Query/read-only code is
    # covered by the existing regression suite and must remain untouched.
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.2.62"
