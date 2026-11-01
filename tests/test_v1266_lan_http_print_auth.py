from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")


def test_print_password_hash_has_non_secure_http_fallback():
    assert "function sha256HexFallback(bytes)" in HTML
    assert 'window.crypto?.subtle' in HTML
    assert 'return sha256HexFallback(data);' in HTML


def test_print_flow_handles_hash_failure_cleanly():
    assert 'toast(t("printAuthUnavailable"))' in HTML
    assert 'printAuthUnavailable: "打印验证失败，请刷新页面后重试"' in HTML
    assert 'printAuthUnavailable: "Print verification failed. Refresh the page and try again."' in HTML
