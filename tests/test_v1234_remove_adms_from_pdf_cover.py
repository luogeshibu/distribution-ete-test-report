from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "web" / "distribution_report.html"


def test_pdf_cover_no_longer_renders_adms_version_row():
    text = TEMPLATE.read_text(encoding="utf-8")
    start = text.index("function updatePrintMeta()")
    end = text.index("const signMeta", start)
    block = text[start:end]

    assert '[t("printPhase"), phaseLabel(m.phase)]' in block
    assert '[t("printDates"), (m.date_from || "") + " ~ " + (m.date_to || "")]' in block
    assert '[t("printLead"), m.lead]' in block
    assert '[t("printTesters"), m.testers]' in block
    assert 'm.adms_version' not in block
    assert 'printAdms' not in block


def test_adms_version_input_and_persistence_are_preserved():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="meta-adms_version"' in text
    assert '"lead", "testers", "adms_version"' in text
