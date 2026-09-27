from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, build_payload


def test_multi_rmu_report_ids_are_individual_and_slash_separated():
    mapping = [
        RmuMapping(rmu_name="JED-CTL-EEH-AH333-22004"),
        RmuMapping(rmu_name="JED-NTH-ABS-AH321-22008"),
    ]
    payload = build_payload(mapping, [], date_value="2026-09-26")
    assert payload["meta_defaults"]["report_id"] == (
        "E2E-JED-CTL-EEH-AH333-22004-20260926 / "
        "E2E-JED-NTH-ABS-AH321-22008-20260926"
    )


def test_single_rmu_report_id_stays_single():
    payload = build_payload(
        [RmuMapping(rmu_name="JED-CTL-EEH-AH333-22004")],
        [],
        date_value="2026-09-26",
    )
    assert payload["meta_defaults"]["report_id"] == "E2E-JED-CTL-EEH-AH333-22004-20260926"
