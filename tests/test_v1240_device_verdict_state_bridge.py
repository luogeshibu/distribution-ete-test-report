from pathlib import Path

from distribution_signal_verifier.live_report_server import _live_script


def test_report_exposes_device_verdict_state_bridge_from_private_state():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert 'window.getDeviceVerdicts = () => ensureDeviceVerdicts();' in report
    assert 'window.setDeviceVerdict = (rmuName, value) =>' in report
    assert 'state.meta.device_verdicts = {};' in report


def test_live_script_uses_bridge_not_private_state_variable():
    js = _live_script('distribution', ['JED-CTL-EEH-AH333-22004'], 60, 'IEC-104', '1.2.40')
    assert "typeof window.getDeviceVerdicts === 'function'" in js
    assert "window.setDeviceVerdict(key, sel.value)" in js
    assert "window.setDeviceVerdict(clean, '')" in js
    assert "typeof state === 'undefined'" not in js


def test_print_sync_reads_the_same_bridged_verdict_object():
    js = _live_script('distribution', ['JED-CTL-EEH-AH333-22004'], 60, 'IEC-104', '1.2.40')
    assert 'const saved = deviceVerdicts();' in js
    assert "cell.textContent = verdictText(saved[key] || saved[idKey] || saved[legacyKey] || '')" in js
