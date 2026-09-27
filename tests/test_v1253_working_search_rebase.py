from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_search_sql_keeps_working_v1247_shape():
    text = (ROOT / "src" / "distribution_signal_verifier" / "distribution_signal_verifier.py").read_text(encoding="utf-8")
    assert "def build_rmu_search_sql" in text
    assert "INSTR(UPPER(TRIM(comb.name)), q.keyword) > 0" in text
    assert "WHERE ROWNUM <= {safe_limit}" in text


def test_working_runtime_config_is_not_replaced_by_empty_upgrade_config():
    import json
    cfg = json.loads((ROOT / "config" / "report_config.json").read_text(encoding="utf-8"))
    oracle = cfg.get("oracle") or {}
    # Regression guard: v1.2.48+ source packaging accidentally blanked the
    # local canonical runtime config, making a known-good search appear broken.
    assert str(oracle.get("host") or "").strip()
    assert str(oracle.get("service") or oracle.get("dsn") or "").strip()
    assert str(oracle.get("user") or "").strip()
    assert str(oracle.get("password") or "").strip()


def test_device_i18n_and_sticky_language_requirements_present():
    report_py = (ROOT / "src" / "distribution_signal_verifier" / "distribution_signal_verifier.py").read_text(encoding="utf-8")
    server_py = (ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py").read_text(encoding="utf-8")
    report_html = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
    history = (ROOT / "web" / "history.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")
    assert "Device Name" in report_py and "Device Type" in report_py
    assert "data-label-en=\"(Not selected)\"" in report_py
    assert "LANG_KEY" in report_html and "DistributionLanguageController" in report_html
    assert "No matching device found" in server_py
    assert "distribution_rmu_e2e_report_search_lang" in history
    assert "distribution_rmu_e2e_report_search_lang" in dashboard
