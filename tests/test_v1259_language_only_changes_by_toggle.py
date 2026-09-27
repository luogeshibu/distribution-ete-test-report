from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
HISTORY = (ROOT / "web" / "history.html").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "web" / "dashboard.html").read_text(encoding="utf-8")
QUERY = (ROOT / "src" / "distribution_signal_verifier" / "distribution_signal_verifier.py").read_text(encoding="utf-8")


def test_saved_report_language_cannot_override_current_operator_language():
    export_start = REPORT.index('function exportState()')
    export_end = REPORT.index('function prepareRmuNavigationHandoff()', export_start)
    assert 'lang: lang' not in REPORT[export_start:export_end]
    assert 'payload.state.lang' not in REPORT
    apply_loaded = REPORT[REPORT.index('function applyLoaded(data)'):REPORT.index('const META_KEYS')]
    assert 'data.lang' not in apply_loaded


def test_only_language_buttons_choose_a_new_language():
    assert 'document.getElementById("lang-zh").onclick = () => setLang("zh")' in REPORT
    assert 'document.getElementById("lang-en").onclick = () => setLang("en")' in REPORT
    assert "$('lang-zh').onclick=()=>setLang('zh')" in HISTORY
    assert "$('lang-en').onclick=()=>setLang('en')" in HISTORY
    assert "$('lang-zh').onclick=()=>setLang('zh')" in DASHBOARD
    assert "$('lang-en').onclick=()=>setLang('en')" in DASHBOARD
    assert 'LANGUAGE_CONTROLLER.select(lang)' in REPORT
    assert 'LANGUAGE_CONTROLLER.select(next)' in HISTORY
    assert 'LANGUAGE_CONTROLLER.select(next)' in DASHBOARD


def test_history_continue_url_does_not_carry_or_restore_task_language():
    start = HISTORY.index('function continueUrl')
    end = HISTORY.index('function setActionMessage', start)
    block = HISTORY[start:end]
    assert "p.set('resume',x.report_uuid)" in block
    assert "p.set('lang'" not in block
    assert "ui_lang" not in block


def test_oracle_query_sql_is_still_read_only():
    assert 'def build_rmu_search_sql' in QUERY
    assert 'def query_rmu_mapping' in QUERY
    assert 'assert_oracle_read_only_sql(sql)' in QUERY


def test_version():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() == '1.2.62'
