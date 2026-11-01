from distribution_signal_verifier.live_report_server import _archive_view_html


def test_frozen_archive_navigation_preserves_report():
    source = '<html><head></head><body><button type="button" id="btn-home">Home</button><button id="btn-history">History</button><button id="btn-dashboard">Dashboard</button><p>Saved result: Pass</p></body></html>'
    result = _archive_view_html(source)
    assert 'href="/">Home</a>' in result
    assert 'href="/history">History</a>' in result
    assert 'href="/dashboard">Dashboard</a>' in result
    assert '<p>Saved result: Pass</p>' in result
    assert '<script' not in result
    assert _archive_view_html(source) == result


def test_formal_archive_overrides_legacy_watermark():
    from distribution_signal_verifier.live_report_server import _formal_print_html
    source = '<html class="print-auth print-draft"><head><style>html.print-draft body::before{content:"DRAFT"}</style></head><body>Pass</body></html>'
    result = _formal_print_html(source)
    assert 'print-auth print-draft print-final' in result
    assert 'html.print-final body::before {content:none!important;display:none!important}' in result
    assert '<body>Pass</body>' in result
