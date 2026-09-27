from pathlib import Path

import distribution_signal_verifier.live_report_server as server
from distribution_signal_verifier.live_report_server import LiveDataProvider, _html_add_root_class
from distribution_signal_verifier.report_store import ReportStore

from test_v1229_report_archive import _payload


def _provider_with_store(store: ReportStore) -> LiveDataProvider:
    provider = LiveDataProvider.__new__(LiveDataProvider)
    provider.report_store = store
    return provider


def test_draft_pdf_generation_keeps_draft_status_and_saved_timestamp(tmp_path, monkeypatch):
    store = ReportStore(tmp_path)
    payload = _payload('<!doctype html><html class="print-auth"><body>DRAFT SNAPSHOT</body></html>')
    payload['is_draft'] = True
    saved = store.save_report(payload, software_version='1.2.35')
    before = store.get_report(saved['report_uuid'])
    assert before is not None
    assert before['is_draft'] == 1
    assert before['pdf_available'] is False

    rendered = {}

    monkeypatch.setattr(server, '_find_print_browser', lambda: Path('browser.exe'))

    def fake_render(html_path: Path, pdf_path: Path) -> bool:
        rendered['html'] = html_path.read_text(encoding='utf-8')
        pdf_path.write_bytes(b'%PDF-1.4\nDRAFT\n')
        return True

    monkeypatch.setattr(server, '_render_pdf_with_browser', fake_render)
    result = _provider_with_store(store).generate_report_pdf(saved['report_uuid'])

    after = store.get_report(saved['report_uuid'])
    assert after is not None
    assert result['pdf_saved'] is True
    assert result['is_draft'] is True
    assert after['is_draft'] == 1
    assert after['updated_at'] == before['updated_at']
    assert after['finalized_at'] == before['finalized_at'] == ''
    assert after['pdf_available'] is True
    assert 'print-draft' in rendered['html']
    assert store.resolve_report_file(saved['report_uuid'], 'pdf').read_bytes().startswith(b'%PDF-1.4')


def test_final_pdf_generation_does_not_add_draft_watermark(tmp_path, monkeypatch):
    store = ReportStore(tmp_path)
    payload = _payload('<!doctype html><html class="print-auth"><body>FINAL SNAPSHOT</body></html>')
    payload['is_draft'] = False
    saved = store.save_report(payload, software_version='1.2.35')
    before = store.get_report(saved['report_uuid'])
    assert before is not None
    assert before['pdf_available'] is False

    rendered = {}
    monkeypatch.setattr(server, '_find_print_browser', lambda: Path('browser.exe'))

    def fake_render(html_path: Path, pdf_path: Path) -> bool:
        rendered['html'] = html_path.read_text(encoding='utf-8')
        pdf_path.write_bytes(b'%PDF-1.4\nFINAL\n')
        return True

    monkeypatch.setattr(server, '_render_pdf_with_browser', fake_render)
    result = _provider_with_store(store).generate_report_pdf(saved['report_uuid'])
    after = store.get_report(saved['report_uuid'])

    assert result['is_draft'] is False
    assert after['is_draft'] == 0
    assert after['updated_at'] == before['updated_at']
    assert 'print-draft' not in rendered['html']


def test_root_html_class_injection_preserves_existing_classes():
    html = '<!doctype html><html lang="zh-CN" class="print-auth"><body></body></html>'
    out = _html_add_root_class(html, 'print-draft')
    assert 'class="print-auth print-draft"' in out


def test_history_offers_pdf_generation_for_any_status():
    history = Path('web/history.html').read_text(encoding='utf-8')
    server_text = Path('src/distribution_signal_verifier/live_report_server.py').read_text(encoding='utf-8')
    assert '生成 PDF' in history
    assert '重新生成 PDF' in history
    assert '查看 PDF' in history
    assert '/generate-pdf' in history
    assert 'generate_report_pdf' in server_text
    assert '/generate-pdf' in server_text
