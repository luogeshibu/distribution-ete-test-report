from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, build_payload


def test_build_payload_tags_points_by_combined_id_for_multi_rmu_groups():
    mappings = [
        RmuMapping(rmu_name="22004", adms_gss_fid="JED-A-22004", combined_id="101"),
        RmuMapping(rmu_name="22005", adms_gss_fid="JED-A-22005", combined_id="102"),
    ]
    rows = [
        {"COMBINED_ID": "101", "POINT_TYPE": "Status Indication", "TABLE_NO": "13560", "DOT_NO": "1000", "SIGNAL_NAME": "22004 Y1 state"},
        {"COMBINED_ID": "102", "POINT_TYPE": "Status Indication", "TABLE_NO": "13560", "DOT_NO": "1001", "SIGNAL_NAME": "22005 Y1 state"},
    ]
    payload = build_payload(mappings, rows, protocol="IEC-104")
    assert payload["points"][0]["rmu_name"] == "22004"
    assert payload["points"][0]["rmu_display_name"] == "JED-A-22004"
    assert payload["points"][1]["rmu_name"] == "22005"
    assert payload["points"][1]["rmu_display_name"] == "JED-A-22005"


def test_template_contains_multi_rmu_3x_and_4x_group_rendering():
    from pathlib import Path
    text = (Path(__file__).parents[1] / "web" / "distribution_report.html").read_text(encoding="utf-8")
    assert "3.' + group.index" in text
    assert '"4." + group.index' in text
    assert "rmu-point-group-title" in text
    assert "renderMultiRmuPointTables" in text
