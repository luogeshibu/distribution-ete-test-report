from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
HISTORY = (ROOT / "web" / "history.html").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")
SERVER = (ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py").read_text(encoding="utf-8")
QUERY = (ROOT / "src" / "distribution_signal_verifier" / "distribution_signal_verifier.py").read_text(encoding="utf-8")


def test_repeated_device_navigation_uses_global_language_only():
    assert 'let lang = LANGUAGE_CONTROLLER.get();' in REPORT
    assert 'LANGUAGE_NAV_KEY' not in REPORT
    assert 'stashNavigationLanguage' not in REPORT
    assert 'prepareLanguageNavigationHandoff' not in REPORT
    assert 'window.addEventListener("pagehide"' not in REPORT


def test_history_and_dashboard_use_same_global_language_authority():
    for text in (HISTORY, DASHBOARD):
        assert 'DistributionLanguageController' in text
        assert 'LANGUAGE_CONTROLLER.get()' in text
        assert 'LANGUAGE_NAV_KEY' not in text
        assert 'stashNavigationLanguage' not in text
        assert "window.addEventListener('pagehide'" not in text


def test_navigation_never_chooses_a_language():
    nav = SERVER[SERVER.index('function navigateSelectedRmus()'):SERVER.index('function openRmu')]
    assert "setLang('zh'" not in nav
    assert "setLang('en'" not in nav
    assert 'DistributionLanguageController.select' not in nav
    assert 'document.getElementById("lang-zh").onclick = () => setLang("zh")' in REPORT
    assert 'document.getElementById("lang-en").onclick = () => setLang("en")' in REPORT


def test_query_contract_remains_unchanged_and_read_only():
    assert "params.set('network', 'distribution');" in SERVER
    assert "params.set('rmu', selectedRmus.join(','));" in SERVER
    assert "fetch('/api/rmu-search?q=' + encodeURIComponent(value)" in SERVER
    assert "params.set('lang'" not in SERVER
    assert 'def build_rmu_search_sql' in QUERY
    assert 'def query_rmu_mapping' in QUERY
    assert 'assert_oracle_read_only_sql(sql)' in QUERY


def test_version():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == '1.2.62'
