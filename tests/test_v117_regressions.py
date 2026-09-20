from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from distribution_signal_verifier.distribution_signal_verifier import build_rmu_search_sql


def test_distribution_template_only_protocol_and_channel_id():
    html = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
    # Actual visible channel rows in the runtime distribution template.
    assert 'data-i18n="chProtocol"' in html
    assert 'data-i18n="chName"' in html
    for key in ("chPort", "chNote", "chBaud", "chDataBits", "chParity", "chStopBits"):
        assert f'<td data-i18n="{key}">' not in html


def test_rmu_search_sql_is_true_partial_match():
    sql, binds = build_rmu_search_sql("346", 50)
    assert binds == {"rmu_keyword": "346"}
    assert "INSTR(UPPER(TRIM(comb.name)), q.keyword) > 0" in sql
    assert 'AS "RMU_NAME"' in sql
    assert 'AS "ADMS_GSS_FID"' in sql
    assert "d5000.dms_combined_device" in sql
    assert "d5000.dms_feeder_device" in sql
    assert "d5000.substation" in sql
    assert "d5000.subcontrolarea" in sql


def test_frontend_has_selectable_candidate_flow():
    from distribution_signal_verifier.distribution_signal_verifier import render_report_text
    from distribution_signal_verifier.live_report_server import _live_script
    html = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
    assert 'id="rmu-suggestions"' in html
    rendered = render_report_text(
        html,
        {"network":"distribution", "rmu_names":[], "meta_defaults":{"channel":{"protocol":"IEC-104"}}},
        extra_before_body_end=_live_script("distribution", [], 60, "IEC-104"),
    )
    assert rendered.count("fetch('/api/rmu-search?q=' + encodeURIComponent(value)") == 1
    assert "function renderSuggestions(items)" in rendered
    assert "button.addEventListener('click'" in rendered
    assert "openRmu(item.rmu_name)" in rendered


def test_final_rendered_iec104_has_no_removed_environment_rows():
    import json, re
    from distribution_signal_verifier.distribution_signal_verifier import render_report_text
    template = (ROOT / "web" / "distribution_report.html").read_text(encoding="utf-8")
    m = re.search(r'<script\s+id="payload"\s+type="application/json">(.*?)</script>', template, re.S)
    payload = json.loads(m.group(1))
    payload["network"] = "distribution"
    payload.setdefault("meta_defaults", {}).setdefault("channel", {})["protocol"] = "IEC-104"
    rendered = render_report_text(template, payload)
    assert '<td data-i18n="chProtocol">' in rendered
    assert '<td data-i18n="chName">' in rendered
    for key in ("chPort", "chNote", "chBaud", "chDataBits", "chParity", "chStopBits"):
        assert f'<td data-i18n="{key}">' not in rendered