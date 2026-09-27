from pathlib import Path

from distribution_signal_verifier.live_report_server import _live_script


def test_live_script_exposes_idempotent_device_verdict_sync():
    js = _live_script('distribution', ['22004', '22008'], 60, 'IEC-104', '1.2.40')
    assert "window.syncDeviceVerdicts = syncDeviceVerdicts" in js
    assert "window.syncPrintDeviceVerdicts = syncPrintDeviceVerdicts" in js
    assert "sel.dataset.verdictBound !== '1'" in js
    assert "cell.textContent = verdictText(saved[key] || saved[legacyKey] || '')" in js


def test_report_forces_verdict_sync_after_resume_and_before_print_snapshot():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert 'applyLoaded(saved);' in report
    assert 'window.syncDeviceVerdicts();' in report
    # One call is in beforeprint and another is in frozenPrintHtml().
    assert report.count('window.syncPrintDeviceVerdicts();') >= 2
    frozen = report.split('function frozenPrintHtml()', 1)[1].split('function archiveSnapshot()', 1)[0]
    assert 'window.syncPrintDeviceVerdicts();' in frozen
    assert frozen.index('window.syncPrintDeviceVerdicts();') < frozen.index('cloneNode(true)')
