from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "web" / "history.html"
DASHBOARD = ROOT / "web" / "dashboard.html"
LANG_KEY = "distribution_rmu_e2e_report_search_lang"


def test_history_has_full_language_toggle_and_shared_global_controller():
    text = HISTORY.read_text(encoding="utf-8")
    assert 'id="lang-zh"' in text
    assert 'id="lang-en"' in text
    assert f"const LANG_KEY='{LANG_KEY}'" in text
    assert 'window.DistributionLanguageController' in text
    assert 'LANGUAGE_CONTROLLER.select(next)' in text
    assert "Test History" in text
    assert "Continue Test" in text
    assert "Draft / Incomplete" in text
    assert "Generate PDF" in text


def test_dashboard_has_full_language_toggle_and_shared_global_controller():
    text = DASHBOARD.read_text(encoding="utf-8")
    assert 'id="lang-zh"' in text
    assert 'id="lang-en"' in text
    assert f"const LANG_KEY='{LANG_KEY}'" in text
    assert 'window.DistributionLanguageController' in text
    assert 'LANGUAGE_CONTROLLER.select(next)' in text
    assert "Test Overview" in text
    assert "Overall Progress" in text
    assert "Statistics by Feeder" in text
    assert "Device Details" in text
    assert "Export Summary Report" in text


def test_dashboard_language_switch_rerenders_loaded_data_without_requery():
    text = DASHBOARD.read_text(encoding="utf-8")
    assert "if(lastData)render(lastData)" in text
    assert "$('lang-zh').onclick=()=>setLang('zh')" in text
    assert "$('lang-en').onclick=()=>setLang('en')" in text


def test_version_is_1248():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.2.62"
