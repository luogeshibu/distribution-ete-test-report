from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / 'web' / 'distribution_report.html').read_text(encoding='utf-8')
HISTORY = (ROOT / 'web' / 'history.html').read_text(encoding='utf-8')
DASHBOARD = (ROOT / 'web' / 'dashboard.html').read_text(encoding='utf-8')
SERVER = (ROOT / 'src' / 'distribution_signal_verifier' / 'live_report_server.py').read_text(encoding='utf-8')
CORE = (ROOT / 'src' / 'distribution_signal_verifier' / 'distribution_signal_verifier.py').read_text(encoding='utf-8')


def test_all_pages_use_same_navigation_durable_language_controller():
    for text in (REPORT, HISTORY, DASHBOARD):
        assert '__distribution_ete_lang__=' in text
        assert 'distribution_ete_language' in text
        assert 'readWindowLanguage()' in text
        assert 'readCookieLanguage()' in text
        assert 'readLocalLanguage(key)' in text
        assert 'window.name' in text
        assert 'document.cookie' in text
        # Same-tab state wins after a full-page add/remove navigation.
        assert ('readWindowLanguage() || readCookieLanguage() || readLocalLanguage(key)' in text or
                "readWindowLanguage()||readCookieLanguage()||readLocalLanguage(key)" in text)


def test_only_explicit_language_buttons_choose_a_new_language():
    assert REPORT.count('setLang("zh")') == 1
    assert REPORT.count('setLang("en")') == 1
    assert HISTORY.count("setLang('zh')") == 1
    assert HISTORY.count("setLang('en')") == 1
    assert DASHBOARD.count("setLang('zh')") == 1
    assert DASHBOARD.count("setLang('en')") == 1
    # Device navigation must not select a language.
    nav = SERVER[SERVER.index('function navigateSelectedRmus()'):SERVER.index('function openRmu')]
    assert 'setLang' not in nav
    assert 'DistributionLanguageController' not in nav
    assert "params.set('lang'" not in nav


def test_report_and_device_handoff_cannot_override_language():
    handoff = REPORT[REPORT.index('function prepareRmuNavigationHandoff()'):REPORT.index('function restoreRmuNavigationHandoff()')]
    assert 'lang:' not in handoff
    assert 'LANG_KEY' not in handoff
    apply_loaded = REPORT[REPORT.index('function applyLoaded(data)'):REPORT.index('const META_KEYS')]
    assert 'data.lang' not in apply_loaded
    assert 'payload.state.lang' not in REPORT


def test_oracle_search_and_readonly_contract_are_unchanged():
    assert 'def build_rmu_search_sql' in CORE
    assert 'def query_rmu_mapping' in CORE
    assert 'assert_oracle_read_only_sql(sql)' in CORE
    assert "fetch('/api/rmu-search?q=' + encodeURIComponent(value)" in SERVER
    assert "params.set('rmu', selectedRmus.join(','))" in SERVER


def test_version():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == '1.2.62'
