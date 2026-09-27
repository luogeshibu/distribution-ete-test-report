from pathlib import Path


def test_pdf_stats_uses_summary_table_and_screen_cards_remain():
    template = Path("web/distribution_report.html").read_text(encoding="utf-8")
    assert 'id="print-stats-table"' in template
    assert 'class="print-stats-table"' in template
    assert 'function printStatsSummaryTable(rows)' in template
    assert 'id="kpi-row"' in template
    assert '#stats .screen-only { display: none !important; }' in template


def test_print_stats_summary_table_contains_expected_columns():
    template = Path("web/distribution_report.html").read_text(encoding="utf-8")
    block = template.split('function printStatsSummaryTable(rows)', 1)[1].split('if (groups.length > 1)', 1)[0]
    for text in ['printStatsDevice', 'kpiPlanned', 'kpiTested', 'kpiUpCoverage', 'kpiDownCoverage', 'Pass with comments', 'Blocked', 'N/A', 'kpiPassRate']:
        assert text in block


def test_print_stats_summary_table_renders_one_row_per_rmu():
    template = Path("web/distribution_report.html").read_text(encoding="utf-8")
    assert 'printRoot.innerHTML = printStatsSummaryTable(groups.map((group) => ({' in template
    assert "label: group.label" in template
