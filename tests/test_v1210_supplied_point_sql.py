from distribution_signal_verifier.distribution_signal_verifier import build_distribution_point_sql, normalize_signal


def test_v1210_uses_supplied_point_sql_rules():
    sql, binds = build_distribution_point_sql([3800193660570625890])
    assert binds == {"combined_id_0": 3800193660570625890}
    assert "yx.reference_name AS signal_key" in sql
    assert "yc.reference_name AS signal_key" in sql
    assert "TO_CHAR(dc.index_no) AS signal_key" in sql
    assert "GET_TAB_NO(p.point_id) AS table_no" in sql
    assert "GET_COL_NO(p.point_id) AS col_no" in sql
    assert "WHERE signal_key IS NOT NULL" in sql
    assert "AND TRIM(signal_key) <> '-1'" in sql
    assert "signal_key AS DOT_NO" in sql
    assert "dot_no AS no" in sql
    assert "13560 AS source_table_no" not in sql


def test_v1210_preserves_report_source_table_labels_outside_sql():
    cases = [
        ("Status Indication", "13560"),
        ("Analog Measurement", "13561"),
        ("Command", "13579"),
    ]
    for i, (point_type, expected) in enumerate(cases, 1):
        point = normalize_signal({
            "point_type": point_type,
            "dot_no": str(i),
            "signal_name": "test",
        }, i)
        assert point["table"] == expected
        assert point["table_no"] == expected
