from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
SERVER = (ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py").read_text(encoding="utf-8")


def test_device_navigation_does_not_have_a_separate_language_handoff():
    assert 'prepareLanguageNavigationHandoff' not in REPORT
    assert 'stashNavigationLanguage' not in REPORT
    assert 'LANGUAGE_NAV_KEY' not in REPORT
    nav = SERVER[SERVER.index('function navigateSelectedRmus()'):SERVER.index('function openRmu')]
    assert 'prepareLanguageNavigationHandoff' not in nav
    assert 'sessionStorage' not in nav


def test_rmu_handoff_never_restores_language_from_saved_test_state():
    start = REPORT.index('function restoreRmuNavigationHandoff()')
    end = REPORT.index('function applyLoaded(data)', start)
    block = REPORT[start:end]
    assert 'payload.state.lang' not in block
    assert 'LANGUAGE_CONTROLLER.select' not in block
    apply_loaded = REPORT[REPORT.index('function applyLoaded(data)'):REPORT.index('function fillMeta()')]
    assert 'data.lang' not in apply_loaded


def test_device_navigation_query_parameters_are_unchanged():
    assert "params.set('network', 'distribution');" in SERVER
    assert "params.set('rmu', selectedRmus.join(','));" in SERVER
    assert "fetch('/api/rmu-search?q=' + encodeURIComponent(value)" in SERVER
    assert "params.set('lang'" not in SERVER
    assert "params.set('ui_lang'" not in SERVER


def test_version():
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == "1.2.62"
