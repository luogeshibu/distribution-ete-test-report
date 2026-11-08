from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest
import distribution_signal_verifier.live_report_server as server
from distribution_signal_verifier.report_store import ReportStore
from test_v1229_report_archive import _payload


def test_empty_pdf_retries_legacy_browser_mode(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(server, "_find_print_browser", lambda: Path("browser.exe"))
    output = tmp_path / "report.pdf"
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        output.write_bytes(b"" if len(calls) == 1 else b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stderr=b"browser diagnostic")
    monkeypatch.setattr(server.subprocess, "run", run)
    assert server._render_pdf_with_browser(tmp_path / "source.html", output)
    assert "--headless=new" in calls[0]
    assert "--headless" in calls[1]
    assert "browser diagnostic" in caplog.text


def test_browser_timeout_is_logged_and_returns_failure(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(server, "_find_print_browser", lambda: Path("browser.exe"))
    def run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 45)
    monkeypatch.setattr(server.subprocess, "run", run)
    assert not server._render_pdf_with_browser(tmp_path / "source.html", tmp_path / "report.pdf")
    assert "timed out" in caplog.text


def test_missing_server_browser_has_actionable_error(tmp_path, monkeypatch):
    store = ReportStore(tmp_path)
    saved = store.save_report(_payload())
    provider = server.LiveDataProvider.__new__(server.LiveDataProvider)
    provider.report_store = store
    monkeypatch.setattr(server, "_find_print_browser", lambda: None)
    with pytest.raises(server.PdfGenerationError) as error:
        provider.generate_report_pdf(saved["report_uuid"])
    assert error.value.code == "pdf_browser_missing"
    assert not store.get_report(saved["report_uuid"])["pdf_available"]


def test_browser_override_supports_custom_install_location(tmp_path, monkeypatch):
    browser = tmp_path / "custom-browser.exe"
    browser.touch()
    monkeypatch.setenv("ETE_PRINT_BROWSER", str(browser))
    assert server._find_print_browser() == browser


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows file sharing semantics")
@pytest.mark.parametrize("legacy_cleanup", [True, False])
def test_locked_browser_log_does_not_fail_completed_pdf(tmp_path, monkeypatch, legacy_cleanup):
    """Reproduce the customer's WinError 32 with a real open Windows file."""
    store = ReportStore(tmp_path)
    saved = store.save_report(_payload())
    provider = server.LiveDataProvider.__new__(server.LiveDataProvider)
    provider.report_store = store
    monkeypatch.setattr(server, "_find_print_browser", lambda: Path("browser.exe"))
    original_temporary_directory = server.tempfile.TemporaryDirectory
    held_files = []
    def temporary_directory(**kwargs):
        kwargs["dir"] = tmp_path
        if legacy_cleanup:
            kwargs["ignore_cleanup_errors"] = False
        return original_temporary_directory(**kwargs)
    monkeypatch.setattr(server.tempfile, "TemporaryDirectory", temporary_directory)
    def run(command, **kwargs):
        profile = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--user-data-dir=")))
        log = profile / "Default" / "Extension Rules" / "000003.log"
        log.parent.mkdir(parents=True)
        held_files.append(log.open("wb"))
        output = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--print-to-pdf=")))
        output.write_bytes(b"%PDF-1.4\ncompleted PDF")
        return SimpleNamespace(returncode=0, stderr=b"")
    monkeypatch.setattr(server.subprocess, "run", run)
    try:
        if legacy_cleanup:
            with pytest.raises(server.PdfGenerationError) as error:
                provider.generate_report_pdf(saved["report_uuid"])
            assert error.value.code == "pdf_file_failed"
        else:
            result = provider.generate_report_pdf(saved["report_uuid"])
            assert result["pdf_saved"] is True
            assert store.get_report(saved["report_uuid"])["pdf_available"] is True
            assert store.resolve_report_file(saved["report_uuid"], "pdf").read_bytes().startswith(b"%PDF-")
    finally:
        for handle in held_files:
            handle.close()
