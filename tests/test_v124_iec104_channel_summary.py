from pathlib import Path

from distribution_signal_verifier.distribution_signal_verifier import RmuMapping, build_payload


def test_iec104_payload_has_one_real_channel_and_no_serial_defaults():
    mapping = [RmuMapping(rmu_name="RMU346", ip="172.16.11.206", protocol_name="IEC-104")]
    payload = build_payload(mapping, [])
    ch = payload["meta_defaults"]["channel"]
    assert ch["primary"]["name"] == "172.16.11.206"
    assert ch["backup"]["name"] == ""
    assert ch["primary"]["baud_rate"] == ""
    assert ch["primary"]["data_bits"] == ""
    assert ch["primary"]["parity"] == ""
    assert ch["primary"]["stop_bits"] == ""


def test_print_summary_does_not_append_serial_9600_or_duplicate_backup_for_104():
    html = Path("web/distribution_report.html").read_text(encoding="utf-8")
    fn = html[html.index("function channelPrintSummary()") : html.index("function fillPhaseVerdictOptions()")]
    assert 'normalizedProtocol.includes("104")' in fn
    assert 'backupId && backupId !== primaryId' in fn
    assert 'return proto + " | " + (primaryId || t("dash"));' in fn
    assert '9600' not in fn