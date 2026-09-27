from pathlib import Path


def test_print_signature_meta_omits_substation_but_keeps_report_id_and_dates():
    template = Path("web/distribution_report.html").read_text(encoding="utf-8")
    block = template.split('const signMeta = document.getElementById("print-sign-meta");', 1)[1].split('const commentBody', 1)[0]
    assert 't("printStation")' not in block
    assert 'm.station' not in block
    assert '[t("printReportId"), m.report_id]' in block
    assert '[t("printDates"), (m.date_from || "") + " ~ " + (m.date_to || "")]' in block
