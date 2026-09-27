from distribution_signal_verifier.distribution_signal_verifier import render_report_text


def test_iec104_final_render_removes_tcp_port_and_note_from_old_template():
    template = '''<!doctype html><html><body><main>
<table id="channel-table"><thead><tr><th>参数</th><th>主</th><th>备</th></tr></thead><tbody>
<tr><td data-i18n="chProtocol">规约</td><td><input id="ch-protocol"></td></tr>
<tr><td data-i18n="chName">通道标识</td><td><input id="ch-primary-name"></td></tr>
<tr><td data-i18n="chPort">TCP 端口</td><td><input id="ch-primary-port"></td></tr>
<tr><td data-i18n="chNote">备注</td><td><input id="ch-primary-note"></td></tr>
</tbody></table>
<script id="payload" type="application/json">{}</script>
<script>const STORAGE_KEY = "x"; const STATION = ""; const ST_ID = ""; const GENERATED_AT = ""; const COUNTS = {};</script>
</main></body></html>'''
    payload = {"network":"distribution", "station":"配网", "rmu_names":[], "distribution_mappings":[],
               "meta_defaults":{"channel":{"protocol":"IEC-104"}}}
    out = render_report_text(template, payload, include_mapping=False)
    assert 'chPort' not in out
    assert 'chNote' not in out
    assert 'ch-primary-port' not in out
    assert 'ch-primary-note' not in out
    assert 'TCP 端口' not in out
    assert '<td data-i18n="chProtocol">规约</td>' in out
    assert '<td data-i18n="chName">通道标识</td>' in out
