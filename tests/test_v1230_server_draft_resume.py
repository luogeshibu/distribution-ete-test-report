from copy import deepcopy
from pathlib import Path

from distribution_signal_verifier.report_store import ReportStore, SCHEMA_VERSION

from test_v1229_report_archive import _payload


def test_draft_save_updates_same_report_instead_of_creating_duplicates(tmp_path):
    store = ReportStore(tmp_path)
    payload = _payload()
    payload['is_draft'] = True
    first = store.save_report(payload, software_version='1.2.30')

    updated = deepcopy(payload)
    updated['report_uuid'] = first['report_uuid']
    updated['snapshot']['meta']['lead'] = 'Tester B'
    updated['snapshot']['points_full'] = [{'id': 'YX-1', 'result': 'Pass'}]
    second = store.save_report(updated, software_version='1.2.30')

    assert second['report_uuid'] == first['report_uuid']
    assert second['is_draft'] is True
    rows = store.list_reports({'status': 'draft'})
    assert len(rows) == 1
    assert rows[0]['lead'] == 'Tester B'
    assert rows[0]['is_draft'] == 1
    assert rows[0]['updated_at']
    assert not rows[0]['finalized_at']


def test_final_print_promotes_existing_draft_and_keeps_same_uuid(tmp_path):
    store = ReportStore(tmp_path)
    draft = _payload()
    draft['is_draft'] = True
    first = store.save_report(draft, software_version='1.2.30')

    final = deepcopy(draft)
    final['report_uuid'] = first['report_uuid']
    final['is_draft'] = False

    def fake_pdf(html_path, pdf_path):
        pdf_path.write_bytes(b'%PDF-1.4\nETE\n')
        return True

    saved = store.save_report(final, software_version='1.2.30', pdf_renderer=fake_pdf)
    assert saved['report_uuid'] == first['report_uuid']
    assert saved['is_draft'] is False
    assert saved['pdf_saved'] is True
    assert saved['finalized_at']
    assert len(store.list_reports({'status': 'draft'})) == 0
    finals = store.list_reports({'status': 'final'})
    assert len(finals) == 1
    assert finals[0]['report_uuid'] == first['report_uuid']


def test_ui_replaces_json_buttons_with_server_draft_save_and_resume():
    report = Path('web/distribution_report.html').read_text(encoding='utf-8')
    history = Path('web/history.html').read_text(encoding='utf-8')
    assert '保存当前报告' in report
    assert 'id="btn-load"' not in report
    assert 'id="file-load"' not in report
    assert 'async function saveCurrentReport()' in report
    assert 'await archiveCurrentReport(true);' in report
    assert 'await archiveCurrentReport(false);' in report
    assert 'RESUME_REPORT_UUID' in report
    assert 'restoreServerDraft()' in report
    assert '继续测试' in history
    assert "p.set('resume',x.report_uuid)" in history
    assert '<option value="draft">草稿 / 未完成</option>' in history


def test_schema_version_keeps_drafts_and_dashboard_migrations():
    assert SCHEMA_VERSION == 3


def test_v1_database_is_migrated_to_v2_without_losing_reports(tmp_path):
    import sqlite3

    db_dir = tmp_path / 'data' / 'database'
    db_dir.mkdir(parents=True)
    db_path = db_dir / 'ete_reports.db'
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            'CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)'
        )
        ReportStore._migration_v1(connection)
        connection.execute(
            'INSERT INTO schema_migrations(version, applied_at) VALUES (1, ?)',
            ('2026-09-26T10:00:00+03:00',),
        )
        connection.execute(
            '''
            INSERT INTO reports(
                report_uuid, report_no, created_at, test_date_from, test_date_to,
                phase, lead, testers, adms_version, verdict_summary, is_draft,
                device_count, software_version, client_ip, pdf_path, html_path, snapshot_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                '11111111-1111-4111-8111-111111111111', 'OLD-REPORT',
                '2026-09-26T10:00:00+03:00', '2026-09-26', '2026-09-26',
                'commission', 'Lead', 'Team', 'ADMS-X', 'pass', 0, 0,
                '1.2.29', '10.0.0.1', '', '', '',
            ),
        )
        connection.commit()
    finally:
        connection.close()

    store = ReportStore(tmp_path)
    rows = store.list_reports({'status': 'final'})
    assert len(rows) == 1
    assert rows[0]['report_no'] == 'OLD-REPORT'
    assert rows[0]['updated_at'] == '2026-09-26T10:00:00+03:00'
    assert rows[0]['finalized_at'] == '2026-09-26T10:00:00+03:00'
