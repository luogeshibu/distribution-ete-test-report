from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / 'web' / 'distribution_report.html').read_text(encoding='utf-8')
HISTORY = (ROOT / 'web' / 'history.html').read_text(encoding='utf-8')
DASHBOARD = (ROOT / 'web' / 'dashboard.html').read_text(encoding='utf-8')
SERVER = (ROOT / 'src' / 'distribution_signal_verifier' / 'live_report_server.py').read_text(encoding='utf-8')
CORE = (ROOT / 'src' / 'distribution_signal_verifier' / 'distribution_signal_verifier.py').read_text(encoding='utf-8')


def test_all_pages_share_one_persistent_language_key_and_controller():
    for text in (REPORT, HISTORY, DASHBOARD):
        assert 'distribution_rmu_e2e_report_search_lang' in text or 'const LANG_KEY = STORAGE_KEY + "_lang"' in text
        assert 'DistributionLanguageController' in text
        assert 'LANGUAGE_CONTROLLER.get()' in text
        assert ('LANGUAGE_CONTROLLER.select(next)' in text) or ('LANGUAGE_CONTROLLER.select(lang)' in text)
        assert 'LANGUAGE_CONTROLLER.sync(next)' in text


def test_legacy_navigation_language_override_is_never_read_or_written():
    for text in (REPORT, HISTORY, DASHBOARD):
        assert 'sessionStorage.getItem(LANG_KEY + "_nav")' not in text
        assert "sessionStorage.getItem(LANG_KEY+'_nav')" not in text
        assert 'sessionStorage.setItem(LANG_KEY + "_nav"' not in text
        assert "sessionStorage.setItem(LANG_KEY+'_nav'" not in text
    # It is safe to delete the stale value once during startup.
    assert 'sessionStorage.removeItem(LANG_KEY + "_nav")' in REPORT


def test_device_navigation_cannot_write_or_choose_language():
    block = SERVER[SERVER.index('function navigateSelectedRmus()'):SERVER.index('function openRmu')]
    assert 'prepareLanguageNavigationHandoff' not in block
    assert 'DistributionLanguageController' not in block
    assert 'setLang' not in block
    assert "params.set('network', 'distribution')" in block
    assert "params.set('rmu', selectedRmus.join(','))" in block


def test_only_explicit_toggle_calls_setlang_with_literal_language():
    assert REPORT.count('setLang("zh")') == 1
    assert REPORT.count('setLang("en")') == 1
    assert HISTORY.count("setLang('zh')") == 1
    assert HISTORY.count("setLang('en')") == 1
    assert DASHBOARD.count("setLang('zh')") == 1
    assert DASHBOARD.count("setLang('en')") == 1


def test_query_and_readonly_contract_unchanged():
    assert 'def build_rmu_search_sql' in CORE
    assert 'def query_rmu_mapping' in CORE
    assert 'assert_oracle_read_only_sql(sql)' in CORE
    assert "fetch('/api/rmu-search?q=' + encodeURIComponent(value)" in SERVER
    assert "params.set('lang'" not in SERVER


def test_version():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == '1.2.62'
