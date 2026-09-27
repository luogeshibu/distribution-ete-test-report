from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / 'web' / 'distribution_report.html'

def test_channel_table_source_has_only_protocol_and_channel_id_rows():
    s = HTML.read_text(encoding='utf-8')
    a = s.index('<table class="channel-table" id="channel-table">')
    b = s.index('</table>', a)
    block = s[a:b]
    assert 'chProtocol' in block
    assert 'chName' in block
    assert 'chPort' not in block
    assert 'chNote' not in block
    assert 'ch-primary-port' not in block
    assert 'ch-primary-note' not in block

def test_defensive_browser_cleanup_is_present():
    s = HTML.read_text(encoding='utf-8')
    assert 'v121-channel-cleanup' in s
    assert '#channel-table tr:has(#ch-primary-port)' in s
    assert "text.includes('tcp 端口')" in s
