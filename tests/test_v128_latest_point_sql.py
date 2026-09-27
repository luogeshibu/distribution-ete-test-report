from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from distribution_signal_verifier.distribution_signal_verifier import build_distribution_point_sql, normalize_signal


def test_latest_point_sql_uses_reference_name_for_yx_yc_and_index_for_yk():
    sql, binds = build_distribution_point_sql([3800193660570625890])
    assert binds == {"combined_id_0": 3800193660570625890}
    assert "yx.reference_name AS signal_key" in sql
    assert "yc.reference_name AS signal_key" in sql
    assert "TO_CHAR(dc.index_no) AS signal_key" in sql
    assert "signal_key AS DOT_NO" in sql
    assert "dot_no AS no" in sql


def test_latest_yx_reference_name_can_be_report_address():
    point = normalize_signal({
        "COMBINED_ID": 1,
        "RMU_NAME": "F05-1509",
        "POINT_TYPE": "Status Indication",
        "DOT_NO": "CB01.OPEN",
        "NO": 17,
        "SIGNAL_NAME": "F05-1509 CB01 Open status",
    }, 1)
    assert point["addr"] == "CB01.OPEN"
    assert point["rmu_name"] == "F05-1509"
