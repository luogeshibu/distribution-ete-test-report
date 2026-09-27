from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "web" / "distribution_report.html"
SERVER = ROOT / "src" / "distribution_signal_verifier" / "live_report_server.py"
SQL_CORE = ROOT / "src" / "distribution_signal_verifier" / "distribution_signal_verifier.py"


def test_language_preference_uses_one_local_storage_backed_controller():
    text = REPORT.read_text(encoding="utf-8")
    assert 'function createLanguageController(key)' in text
    assert 'const saved = localStorage.getItem(key);' in text
    assert 'localStorage.setItem(key, current)' in text
    assert 'let lang = LANGUAGE_CONTROLLER.get();' in text
    # Legacy nav override is only deleted, never read or written.
    assert 'sessionStorage.getItem(LANG_KEY + "_nav")' not in text
    assert 'sessionStorage.setItem(LANG_KEY + "_nav"' not in text


def test_restore_does_not_overwrite_current_language():
    text = REPORT.read_text(encoding="utf-8")
    start = text.index("function applyLoaded(data)")
    end = text.index("const META_KEYS", start)
    block = text[start:end]
    assert 'data.lang' not in block
    assert 'LANGUAGE_CONTROLLER.select' not in block


def test_language_fix_does_not_add_language_to_device_query_navigation():
    text = SERVER.read_text(encoding="utf-8")
    start = text.index("function navigateSelectedRmus()")
    end = text.index("function openRmu", start)
    block = text[start:end]
    assert "params.set('lang'" not in block
    assert "params.set('network', 'distribution')" in block
    assert "params.set('rmu', selectedRmus.join(','))" in block


def test_oracle_query_source_keeps_read_only_guard():
    text = SQL_CORE.read_text(encoding="utf-8")
    assert "def assert_oracle_read_only_sql" in text
    assert "def build_rmu_search_sql" in text
