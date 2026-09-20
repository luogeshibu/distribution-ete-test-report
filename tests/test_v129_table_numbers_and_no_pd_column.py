from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import build_distribution_point_sql, normalize_signal


def test_three_remote_source_table_numbers_are_returned():
    sql, _ = build_distribution_point_sql([123])
    assert "13560 AS source_table_no" in sql
    assert "'Analog Measurement', 13561, 2" in sql
    assert "'Command', 13579, 3" in sql
    assert "p.source_table_no AS table_no" in sql
    assert "SELECT combined_id, rmu_name, point_type, table_no" in sql


def test_normalized_signal_uses_returned_table_number_not_generic_three_remote():
    point = normalize_signal({
        "point_type": "Status Indication",
        "table_no": 13560,
        "dot_no": "1000",
        "signal_name": "22004 Y1/Lock/Unlock indication value",
    }, 1)
    assert point["table"] == "13560"
    assert point["table_no"] == "13560"


def test_signal_points_table_has_no_standalone_pd_column():
    html = (Path(__file__).parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")
    assert '<th class="no-print">PD</th>' not in html
    assert 'const tdPd = document.createElement("td")' not in html
    assert "tdPd" not in html