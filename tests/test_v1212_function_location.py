from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from distribution_signal_verifier.distribution_signal_verifier import (
    build_rmu_sql, build_rmu_search_sql, normalize_mapping, _render_mapping_section,
)


def test_live_rmu_sql_uses_supplied_function_location_and_regex_rule():
    sql, binds = build_rmu_sql(["7324"])
    assert binds == {"rmu_0": "7324"}
    assert "comb.st_string_07" in sql
    assert 'rb.st_string_07 AS "FUNCTION LOCATION"' in sql
    assert "REGEXP_LIKE" in sql
    assert "'(^|[^0-9])' || TRIM(r.rmu_name) || '([^0-9]|$)'" in sql


def test_search_sql_also_returns_function_location():
    sql, _ = build_rmu_search_sql("7324")
    assert 'comb.st_string_07 AS "FUNCTION LOCATION"' in sql


def test_mapping_and_table_put_function_location_before_ip():
    m = normalize_mapping({"ADMS_GSS_FID":"JED-CTL-ADF-AH315-B7324", "FUNCTION LOCATION":"4200-JCS-007324", "IP":"172.16.11.206", "PROTOCOL_NAME":"IEC-104"})
    assert m.function_location == "4200-JCS-007324"
    html = _render_mapping_section([m], ["B7324"])
    assert html.index("FUNCTION LOCATION") < html.index(">IP<")
    assert html.index("4200-JCS-007324") < html.index("172.16.11.206")
