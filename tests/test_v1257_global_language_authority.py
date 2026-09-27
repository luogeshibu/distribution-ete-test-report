from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
HISTORY = (ROOT / "web" / "history.html").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")


def test_local_storage_controller_is_the_only_persistent_language_authority():
    for text in (REPORT, HISTORY, DASHBOARD):
        assert 'DistributionLanguageController' in text
        assert 'localStorage.getItem' in text
        assert 'localStorage.setItem' in text
        assert 'sessionStorage.getItem(LANG_KEY' not in text
        assert 'sessionStorage.setItem(LANG_KEY' not in text


def test_normal_test_operations_cannot_change_language_preference():
    start = REPORT.index('function persist()')
    end = REPORT.index('function saveLanguagePreference', start)
    persist_block = REPORT[start:end]
    assert 'LANGUAGE_CONTROLLER.select' not in persist_block
    start = REPORT.index('function setLang(next)')
    end = REPORT.index('function freshClientState', start)
    set_lang_block = REPORT[start:end]
    assert 'saveLanguagePreference();' in set_lang_block


def test_all_pages_follow_explicit_language_change_across_tabs_without_rewriting_it():
    assert 'window.addEventListener("storage", (event) =>' in REPORT
    assert "window.addEventListener('storage',(event)=>" in HISTORY
    assert "window.addEventListener('storage',(event)=>" in DASHBOARD
    assert 'LANGUAGE_CONTROLLER.sync(next)' in REPORT
    assert 'LANGUAGE_CONTROLLER.sync(next)' in HISTORY
    assert 'LANGUAGE_CONTROLLER.sync(next)' in DASHBOARD


def test_release_version():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == '1.2.62'
