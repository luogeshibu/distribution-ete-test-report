from pathlib import Path

from distribution_signal_verifier.live_report_server import _live_script


def test_report_exposes_one_time_rmu_navigation_handoff():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert 'window.prepareRmuNavigationHandoff = prepareRmuNavigationHandoff;' in report
    assert 'state: exportState(),' in report
    assert 'report_uuid: currentReportUuid || "",' in report
    assert 'source_default_report_id: String(RAW.meta_defaults?.report_id || ""),' in report
    assert 'active_tab: activeTab,' in report
    assert 'applyLoaded(payload.state);' in report
    assert 'rememberReportUuid(payload.report_uuid || "", !!payload.report_finalized);' in report


def test_handoff_is_one_time_and_does_not_restore_on_normal_reopen():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    read_pos = report.index('raw = sessionStorage.getItem(key) || "";')
    remove_pos = report.index('sessionStorage.removeItem(key);', read_pos)
    apply_pos = report.index('applyLoaded(payload.state);', remove_pos)
    assert read_pos < remove_pos < apply_pos
    assert 'ageMs > 10 * 60 * 1000' in report
    assert 'url.searchParams.delete("handoff");' in report


def test_live_rmu_navigation_carries_handoff_token_before_reload():
    js = _live_script(
        'distribution',
        ['JED-CTL-EEH-AH333-22004'],
        60,
        'IEC-104',
        '1.2.41',
    )
    assert 'const hadSelectedRmusAtLoad = selectedRmus.length > 0;' in js
    assert "hadSelectedRmusAtLoad && selectedRmus.length > 0" in js
    assert "typeof window.prepareRmuNavigationHandoff === 'function'" in js
    assert "const handoff = window.prepareRmuNavigationHandoff();" in js
    assert "if (handoff) params.set('handoff', handoff);" in js
    assert "window.location.assign('/?' + params.toString());" in js


def test_auto_generated_report_id_refreshes_for_new_device_but_custom_id_is_preserved():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    assert 'savedReportId === sourceDefaultReportId' in report
    assert 'state.meta.report_id = String(RAW.meta_defaults.report_id);' in report
