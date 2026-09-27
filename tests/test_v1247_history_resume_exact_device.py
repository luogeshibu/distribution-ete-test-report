from pathlib import Path

from distribution_signal_verifier.report_store import ReportStore


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "web" / "history.html"


def test_history_continue_uses_full_fid_not_short_duplicate_name():
    text = HISTORY.read_text(encoding="utf-8")
    assert "function resumeSelector(d)" in text
    assert "return 'fid:'+display" in text
    assert "devices.map(resumeSelector)" in text
    assert "devices.map(d=>String(d.rmu_name" not in text


def test_history_resume_can_rebuild_fid_from_saved_hierarchy():
    text = HISTORY.read_text(encoding="utf-8")
    assert "scope.concat([rmu]).join('-')" in text


def test_report_store_prefers_per_device_fid_verdict_for_duplicate_short_names():
    verdicts = {
        "fid:JED-CTL-ADF-AH315-6": "pass",
        "fid:JED-CTL-ANS-AH325-6": "fail",
        # A legacy short-name value must not override exact per-device keys.
        "6": "conditional",
    }
    a = {"rmu_name": "6", "adms_gss_fid": "JED-CTL-ADF-AH315-6"}
    b = {"rmu_name": "6", "adms_gss_fid": "JED-CTL-ANS-AH325-6"}
    assert ReportStore._device_verdict_value(verdicts, a) == "pass"
    assert ReportStore._device_verdict_value(verdicts, b) == "fail"
    assert ReportStore._summary_verdict(verdicts, [a, b]) == "fail"
