import pytest
from distribution_signal_verifier.report_store import ReportStore
from test_v1229_report_archive import _payload


@pytest.mark.parametrize("devices", [None, [], [{}], [{"rmu_name": "  "}]])
@pytest.mark.parametrize("draft", [True, False])
def test_empty_device_report_does_not_create_archive(tmp_path, devices, draft):
    store = ReportStore(tmp_path)
    payload = _payload()
    payload["snapshot"]["distribution_mappings"] = devices
    payload["is_draft"] = draft
    with pytest.raises(ValueError, match="Select at least one device"):
        store.save_report(payload)
    assert store.list_reports({}) == []
    assert not list(store.reports_dir.rglob("snapshot.json"))
