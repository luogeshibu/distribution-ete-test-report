"""Build a distribution-network signal verification report.

The existing ``e2e_report.html`` is used as the report UI. This module
prepares the distribution payload and injects an RMU mapping section, so the
existing point search, selection, statistics, JSON save and print workflow
remain available.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_TEMPLATE_CANDIDATES = (
    Path(r"D:\Workspace\配网报告\e2e_report.html"),
    Path(r"D:\Workspace\e2e_report.html"),
)
DEFAULT_TEMPLATE = next((path for path in _TEMPLATE_CANDIDATES if path.exists()), _TEMPLATE_CANDIDATES[0])
DEFAULT_PROTOCOL = "IEC 101"
SUPPORTED_KINDS = {"YX", "YC", "YK", "YP", "PD", "SP"}


@dataclass(frozen=True)
class RmuMapping:
    combined_id: Any = None
    adms_gss_fid: str = ""
    rmu_name: str = ""
    combined_type: Any = None
    rmu_type: str = ""
    smart_type: str = ""
    nop: str = ""
    function_location: str = ""
    feeder_name: str = ""
    substation_name: str = ""
    subcontrolarea_name: str = ""
    ip: str = ""
    protocol_name: str = ""


class InputError(ValueError):
    """Raised when an input file cannot be converted to report data."""


def _first(row: Mapping[str, Any], *names: str, default: Any = "") -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return default


def _clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_mapping(row: Mapping[str, Any]) -> RmuMapping:
    return RmuMapping(
        combined_id=_first(row, "combined_id", "COMBINED_ID", "com_id", "COM_ID", "id", default=None),
        adms_gss_fid=_clean_text(_first(row, "adms_gss_fid", "ADMS_GSS_FID")),
        rmu_name=_clean_text(_first(row, "rmu_name", "RMU_NAME", "name")),
        combined_type=_first(row, "combined_type", "COMBINED_TYPE", default=None),
        rmu_type=_clean_text(_first(row, "rmu_type", "RMU_TYPE")),
        smart_type=_clean_text(_first(row, "smart_type", "SMART_TYPE", "smart", "SMART")),
        nop=_clean_text(_first(row, "nop", "NOP")),
        function_location=_clean_text(_first(row, "function_location", "FUNCTION LOCATION", "FUNCTION_LOCATION", "st_string_07", "ST_STRING_07")),
        feeder_name=_clean_text(_first(row, "feeder_name", "FEEDER_NAME")),
        substation_name=_clean_text(
            _first(row, "substation_name", "SUBSTATION_NAME")
        ),
        subcontrolarea_name=_clean_text(
            _first(row, "subcontrolarea_name", "SUBCONTROLAREA_NAME")
        ),
        ip=_clean_text(_first(row, "ip", "IP", "net_description1")),
        protocol_name=_clean_text(
            _first(row, "protocol_name", "PROTOCOL_NAME", "protocol")
        ),
    )


def load_json_rows(path: Path) -> list[Mapping[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"无法读取 JSON：{path}\n{exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"JSON 格式错误：{path}\n{exc}") from exc

    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = next(
            (data[key] for key in ("rows", "mappings", "points", "signals", "data") if isinstance(data.get(key), list)),
            [data],
        )
    else:
        raise InputError(f"JSON 顶层必须是对象或数组：{path}")
    if not all(isinstance(row, Mapping) for row in rows):
        raise InputError(f"JSON 数组中每一项都必须是对象：{path}")
    return list(rows)


def build_rmu_sql(rmu_names: Sequence[str]) -> tuple[str, dict[str, str]]:
    """Create the supplied RMU-to-ADMS identity query with Oracle binds."""

    names = [_clean_text(name) for name in rmu_names if _clean_text(name)]
    if not names:
        raise InputError("至少要提供一个 RMU 名称")
    list_sql = "\n            UNION ALL\n            ".join(
        f"SELECT :rmu_{index} AS rmu_name FROM dual"
        for index in range(len(names))
    )
    sql = f"""
WITH rmu_list AS
(
    {list_sql}
), rmu_base AS
(
    SELECT
        comb.id AS combined_id,
        TRIM(comb.name) AS rmu_name,
        comb.combined_type,
        comb.st_string_07,
        TRIM(feeder.name) AS feeder_name,
        TRIM(sub.name) AS substation_name,
        TRIM(sca.name) AS subcontrolarea_name
    FROM rmu_list r
    LEFT JOIN d5000.dms_combined_device comb
      ON REGEXP_LIKE(
          TRIM(comb.name),
          '(^|[^0-9])' || TRIM(r.rmu_name) || '([^0-9]|$)'
      )
    LEFT JOIN d5000.dms_feeder_device feeder
      ON feeder.id = comb.feeder_id
    LEFT JOIN d5000.substation sub
      ON sub.id = feeder.st_id
    LEFT JOIN d5000.subcontrolarea sca
      ON sca.id = sub.subarea_id
)
SELECT
    rb.combined_id AS "COMBINED_ID",
    TRIM(rb.subcontrolarea_name || '-' || rb.substation_name || '-' ||
         rb.feeder_name || '-' || rb.rmu_name) AS "ADMS_GSS_FID",
    rb.rmu_name AS "RMU_NAME",
    rb.feeder_name AS "FEEDER_NAME",
    rb.substation_name AS "SUBSTATION_NAME",
    rb.subcontrolarea_name AS "SUBCONTROLAREA_NAME",
    rb.combined_type AS "COMBINED_TYPE",
    rb.st_string_07 AS "FUNCTION LOCATION",
    REGEXP_REPLACE(
        REGEXP_SUBSTR(sm.display_value, '^[^(]+'),
        '-NOP$', ''
    ) AS "RMU_TYPE",
    CASE
        WHEN rb.combined_type BETWEEN 21 AND 25
          OR rb.combined_type BETWEEN 41 AND 45
          OR rb.combined_type BETWEEN 61 AND 63
        THEN 'SMART'
        WHEN rb.combined_type IS NOT NULL THEN 'NONSMART'
        ELSE NULL
    END AS "SMART_TYPE",
    CASE
        WHEN rb.combined_type BETWEEN 31 AND 35
          OR rb.combined_type BETWEEN 41 AND 45
        THEN 'NOP'
        ELSE NULL
    END AS "NOP"
FROM rmu_base rb
LEFT JOIN d5000.sys_menu_info sm
  ON sm.menu_name = 'Switch station type'
 AND sm.actual_value = rb.combined_type
ORDER BY rb.rmu_name
""".strip()
    return sql, {f"rmu_{index}": name for index, name in enumerate(names)}



def build_rmu_id_sql(combined_ids: Sequence[Any]) -> tuple[str, dict[str, Any]]:
    """Load explicitly selected distribution devices by exact COMBINED_ID.

    The browser search is fuzzy, but once an operator clicks one candidate the
    selected device must be exact.  Using COMBINED_ID avoids the ambiguity of
    short RMU names such as ``6`` that may exist on many feeders.
    """

    ids = [_clean_text(value) for value in combined_ids if _clean_text(value)]
    if not ids:
        raise InputError("至少要提供一个 COMBINED_ID")
    list_sql = "\n            UNION ALL\n            ".join(
        f"SELECT :combined_id_{index} AS combined_id FROM dual"
        for index in range(len(ids))
    )
    sql = f"""
WITH combined_list AS
(
    {list_sql}
)
SELECT
    comb.id AS "COMBINED_ID",
    TRIM(sca.name || '-' || sub.name || '-' || feeder.name || '-' || comb.name) AS "ADMS_GSS_FID",
    TRIM(comb.name) AS "RMU_NAME",
    TRIM(feeder.name) AS "FEEDER_NAME",
    TRIM(sub.name) AS "SUBSTATION_NAME",
    TRIM(sca.name) AS "SUBCONTROLAREA_NAME",
    comb.combined_type AS "COMBINED_TYPE",
    comb.st_string_07 AS "FUNCTION LOCATION",
    REGEXP_REPLACE(
        REGEXP_SUBSTR(sm.display_value, '^[^(]+'),
        '-NOP$', ''
    ) AS "RMU_TYPE",
    CASE
        WHEN comb.combined_type BETWEEN 21 AND 25
          OR comb.combined_type BETWEEN 41 AND 45
          OR comb.combined_type BETWEEN 61 AND 63
        THEN 'SMART'
        WHEN comb.combined_type IS NOT NULL THEN 'NONSMART'
        ELSE NULL
    END AS "SMART_TYPE",
    CASE
        WHEN comb.combined_type BETWEEN 31 AND 35
          OR comb.combined_type BETWEEN 41 AND 45
        THEN 'NOP'
        ELSE NULL
    END AS "NOP"
FROM combined_list l
JOIN d5000.dms_combined_device comb
  ON TO_CHAR(comb.id) = TRIM(l.combined_id)
LEFT JOIN d5000.dms_feeder_device feeder
  ON feeder.id = comb.feeder_id
LEFT JOIN d5000.substation sub
  ON sub.id = feeder.st_id
LEFT JOIN d5000.subcontrolarea sca
  ON sca.id = sub.subarea_id
LEFT JOIN d5000.sys_menu_info sm
  ON sm.menu_name = 'Switch station type'
 AND sm.actual_value = comb.combined_type
""".strip()
    return sql, {f"combined_id_{index}": value for index, value in enumerate(ids)}


def _mapping_selector(item: RmuMapping) -> str:
    """Return the stable browser selector used for add/remove/verdict state."""

    combined_id = _clean_text(item.combined_id)
    if combined_id:
        return f"id:{combined_id}"
    if _clean_text(item.adms_gss_fid):
        return f"fid:{_clean_text(item.adms_gss_fid)}"
    return _clean_text(item.rmu_name)


def build_rmu_search_sql(keyword: str, limit: int = 50) -> tuple[str, dict[str, Any]]:
    """Search RMUs by a partial name for the browser selector."""

    value = _clean_text(keyword)
    if not value:
        raise InputError("请输入环网柜名称关键字")
    safe_limit = max(1, min(int(limit), 100))
    # Keep the bind in a one-row CTE so Oracle sees it only once.  The search
    # itself is intentionally a substring match: entering 346 returns 34661,
    # OLD_346xx, etc., and the operator then selects the required RMU.
    sql = f"""
WITH search_arg AS (
    SELECT UPPER(TRIM(:rmu_keyword)) AS keyword FROM dual
)
SELECT * FROM (
    SELECT
        comb.id AS "COMBINED_ID",
        TRIM(sca.name || '-' || sub.name || '-' || feeder.name || '-' || comb.name) AS "ADMS_GSS_FID",
        TRIM(comb.name) AS "RMU_NAME",
        TRIM(feeder.name) AS "FEEDER_NAME",
        TRIM(sub.name) AS "SUBSTATION_NAME",
        TRIM(sca.name) AS "SUBCONTROLAREA_NAME",
        comb.combined_type AS "COMBINED_TYPE",
        comb.st_string_07 AS "FUNCTION LOCATION",
        REGEXP_REPLACE(REGEXP_SUBSTR(sm.display_value, '^[^(]+'), '-NOP$', '') AS "RMU_TYPE",
        CASE
            WHEN comb.combined_type BETWEEN 21 AND 25
              OR comb.combined_type BETWEEN 41 AND 45
              OR comb.combined_type BETWEEN 61 AND 63 THEN 'SMART'
            WHEN comb.combined_type IS NOT NULL THEN 'NONSMART'
            ELSE NULL
        END AS "SMART_TYPE",
        CASE
            WHEN comb.combined_type BETWEEN 31 AND 35
              OR comb.combined_type BETWEEN 41 AND 45 THEN 'NOP'
            ELSE NULL
        END AS "NOP"
    FROM d5000.dms_combined_device comb
    CROSS JOIN search_arg q
    LEFT JOIN d5000.dms_feeder_device feeder ON feeder.id = comb.feeder_id
    LEFT JOIN d5000.substation sub ON sub.id = feeder.st_id
    LEFT JOIN d5000.subcontrolarea sca ON sca.id = sub.subarea_id
    LEFT JOIN d5000.sys_menu_info sm
      ON sm.menu_name = 'Switch station type'
     AND sm.actual_value = comb.combined_type
    WHERE INSTR(UPPER(TRIM(comb.name)), q.keyword) > 0
    ORDER BY
      CASE WHEN UPPER(TRIM(comb.name)) = q.keyword THEN 0
           WHEN INSTR(UPPER(TRIM(comb.name)), q.keyword) = 1 THEN 1
           ELSE 2 END,
      TRIM(comb.name)
)
WHERE ROWNUM <= {safe_limit}
""".strip()
    return sql, {"rmu_keyword": value}




def build_smart_inventory_sql(
    substation: str = "",
    feeder: str = "",
    subcontrolarea: str = "",
) -> tuple[str, dict[str, Any]]:
    """Build an inventory query for SMART distribution combined devices.

    This is intentionally separate from the existing RMU selector/query path.
    It is used only by the management dashboard to calculate the population
    that should be covered by ETE testing for a station/feeder scope.
    """

    station_value = _clean_text(substation)
    feeder_value = _clean_text(feeder)
    area_value = _clean_text(subcontrolarea)
    sql = """
SELECT
    comb.id AS "COMBINED_ID",
    TRIM(sca.name || '-' || sub.name || '-' || feeder.name || '-' || comb.name) AS "ADMS_GSS_FID",
    TRIM(comb.name) AS "RMU_NAME",
    TRIM(feeder.name) AS "FEEDER_NAME",
    TRIM(sub.name) AS "SUBSTATION_NAME",
    TRIM(sca.name) AS "SUBCONTROLAREA_NAME",
    comb.combined_type AS "COMBINED_TYPE",
    comb.st_string_07 AS "FUNCTION LOCATION",
    REGEXP_REPLACE(REGEXP_SUBSTR(sm.display_value, '^[^(]+'), '-NOP$', '') AS "RMU_TYPE",
    'SMART' AS "SMART_TYPE",
    CASE
        WHEN comb.combined_type BETWEEN 41 AND 45 THEN 'NOP'
        ELSE NULL
    END AS "NOP"
FROM d5000.dms_combined_device comb
LEFT JOIN d5000.dms_feeder_device feeder ON feeder.id = comb.feeder_id
LEFT JOIN d5000.substation sub ON sub.id = feeder.st_id
LEFT JOIN d5000.subcontrolarea sca ON sca.id = sub.subarea_id
LEFT JOIN d5000.sys_menu_info sm
  ON sm.menu_name = 'Switch station type'
 AND sm.actual_value = comb.combined_type
WHERE (
       comb.combined_type BETWEEN 21 AND 25
    OR comb.combined_type BETWEEN 41 AND 45
    OR comb.combined_type BETWEEN 61 AND 63
)
  AND (:substation = '' OR UPPER(TRIM(sub.name)) LIKE UPPER(:substation_like))
  AND (:feeder = '' OR UPPER(TRIM(feeder.name)) LIKE UPPER(:feeder_like))
  AND (:subcontrolarea = '' OR UPPER(TRIM(sca.name)) LIKE UPPER(:subcontrolarea_like))
ORDER BY TRIM(sca.name), TRIM(sub.name), TRIM(feeder.name), TRIM(comb.name)
""".strip()
    return sql, {
        "substation": station_value,
        "substation_like": f"%{station_value}%",
        "feeder": feeder_value,
        "feeder_like": f"%{feeder_value}%",
        "subcontrolarea": area_value,
        "subcontrolarea_like": f"%{area_value}%",
    }


def build_distribution_point_sql(combined_ids: Sequence[Any]) -> tuple[str, dict[str, Any]]:
    """Build the supplied COM_ID three-remote-point query with Oracle binds."""

    ids = [value for value in combined_ids if value not in (None, "")]
    if not ids:
        raise InputError("至少要提供一个 COM_ID")
    list_sql = ", ".join(f":combined_id_{index}" for index in range(len(ids)))
    sql = f"""
WITH combined_list AS
(
    SELECT COLUMN_VALUE AS combined_id
    FROM TABLE
    (
        SYS.ODCINUMBERLIST
        (
            {list_sql}
        )
    )
),
point_info AS
(
    SELECT
        comb.id AS combined_id,
        comb.name AS rmu_name,
        'Status Indication' AS point_type,
        1 AS sort_no,
        yx.yx_id AS point_id,
        yx.dot_no,
        yx.reference_name AS signal_key,
        yx.reference_name
    FROM combined_list l
    JOIN d5000.dms_combined_device comb
      ON comb.id=l.combined_id
    JOIN d5000.dms_fes_yx_define yx
      ON yx.combined_id=comb.id
    WHERE yx.dot_no>0

    UNION ALL

    SELECT
        comb.id,
        comb.name,
        'Analog Measurement',
        2,
        yc.yc_id,
        yc.dot_no,
        yc.reference_name AS signal_key,
        yc.reference_name
    FROM combined_list l
    JOIN d5000.dms_combined_device comb
      ON comb.id=l.combined_id
    JOIN d5000.dms_fes_yc_define yc
      ON yc.combined_id=comb.id
    WHERE yc.dot_no>0

    UNION ALL

    SELECT
        comb.id,
        comb.name,
        'Command',
        3,
        dc.psid,
        dc.index_no,
        TO_CHAR(dc.index_no) AS signal_key,
        CAST(NULL AS VARCHAR2(200))
    FROM combined_list l
    JOIN d5000.dms_combined_device comb
      ON comb.id=l.combined_id
    JOIN d5000.dms_send_dc dc
      ON dc.combined_id=comb.id
    WHERE dc.index_no>0
),
point_parse AS
(
    SELECT
        p.*,
        GET_TAB_NO(p.point_id) AS table_no,
        GET_COL_NO(p.point_id) AS col_no,
        p.point_id
        - GET_COL_NO(p.point_id) * POWER(2,32) AS device_id
    FROM point_info p
),
signal_data AS
(
    SELECT
        p.combined_id,
        p.rmu_name,
        p.point_type,
        p.signal_key,
        p.dot_no,
        TRIM
        (
            p.rmu_name || ' ' ||
            NVL
            (
                CASE
                    WHEN p.table_no=13502 THEN cb.name
                    WHEN p.table_no=13514 THEN gd.name
                    WHEN p.table_no=13533 THEN rs.name
                    WHEN p.table_no=13534 THEN vi.name
                END,
                ''
            ) || ' ' ||
            CASE
                WHEN p.point_type='Command' THEN 'CMD'
                ELSE NVL(sci.column_name_chn, '')
            END
        ) AS signal_name
    FROM point_parse p
    LEFT JOIN d5000.dms_cb_device cb
      ON p.table_no=13502
     AND cb.id=p.device_id
    LEFT JOIN d5000.dms_ground_disconnector gd
      ON p.table_no=13514
     AND gd.id=p.device_id
    LEFT JOIN d5000.dms_relay_sig rs
      ON p.table_no=13533
     AND rs.id=p.device_id
    LEFT JOIN d5000.dms_value_info vi
      ON p.table_no=13534
     AND vi.id=p.device_id
    LEFT JOIN d5000.sys_column_info sci
      ON sci.table_id=p.table_no
     AND sci.column_id=p.col_no
)
SELECT
    combined_id,
    rmu_name,
    point_type,
    signal_key AS DOT_NO,
    dot_no AS no,
    signal_name
FROM signal_data
WHERE signal_key IS NOT NULL
  AND TRIM(signal_key) <> '-1'
ORDER BY
    combined_id,
    CASE point_type
        WHEN 'Status Indication' THEN 1
        WHEN 'Analog Measurement' THEN 2
        WHEN 'Command' THEN 3
    END,
    no
""".strip()
    return sql, {f"combined_id_{index}": value for index, value in enumerate(ids)}

def build_distribution_protocol_sql(combined_ids: Sequence[Any]) -> tuple[str, dict[str, Any]]:
    """Build the supplied COM_ID channel/protocol query with Oracle binds."""

    ids = [value for value in combined_ids if value not in (None, "")]
    if not ids:
        raise InputError("至少要提供一个 COM_ID")
    list_sql = ", ".join(f":combined_id_{index}" for index in range(len(ids)))
    sql = f"""
WITH combined_list AS
(
    SELECT COLUMN_VALUE AS combined_id
    FROM TABLE(SYS.ODCINUMBERLIST({list_sql}))
)
SELECT DISTINCT
    comb.id AS COM_ID,
    comb.name AS RMU_NAME,
    ch.net_description1 AS IP,
    NVL(sm.display_value, TO_CHAR(ch.proto_type)) AS PROTOCOL_NAME
FROM combined_list l
JOIN d5000.dms_combined_device comb ON comb.id = l.combined_id
LEFT JOIN d5000.dms_terminal_info te ON te.combined_id = comb.id
LEFT JOIN d5000.dms_channel_info ch ON ch.terminal_id = te.id
LEFT JOIN d5000.sys_menu_info sm
  ON sm.menu_name = 'FES_COMM_PROTOCOL'
 AND sm.actual_value = ch.proto_type
ORDER BY comb.id
""".strip()
    return sql, {f"combined_id_{index}": value for index, value in enumerate(ids)}


def _oracle_sql_code_only(sql: str) -> str:
    """Return SQL code with comments/string literals blanked for safety checks.

    The application is intentionally Oracle read-only.  This scanner avoids
    false positives from words such as UPDATE inside comments or quoted text.
    """

    text = str(sql or "")
    out: list[str] = []
    i = 0
    state = "code"
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if ch == "'":
                state = "single"
                out.append(" " )
            elif ch == '"':
                state = "double"
                out.append(" " )
            elif ch == "-" and nxt == "-":
                state = "line_comment"
                out.extend((" ", " "))
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block_comment"
                out.extend((" ", " "))
                i += 1
            else:
                out.append(ch)
        elif state == "single":
            out.append("\n" if ch == "\n" else " " )
            if ch == "'":
                if nxt == "'":
                    out.append(" " )
                    i += 1
                else:
                    state = "code"
        elif state == "double":
            out.append("\n" if ch == "\n" else " " )
            if ch == '"':
                if nxt == '"':
                    out.append(" " )
                    i += 1
                else:
                    state = "code"
        elif state == "line_comment":
            if ch == "\n":
                state = "code"
                out.append("\n")
            else:
                out.append(" " )
        else:  # block_comment
            if ch == "*" and nxt == "/":
                out.extend((" ", " "))
                i += 1
                state = "code"
            else:
                out.append("\n" if ch == "\n" else " " )
        i += 1
    return "".join(out)


def assert_oracle_read_only_sql(sql: str) -> None:
    """Reject anything that is not a single read-only SELECT/WITH query."""

    code = _oracle_sql_code_only(sql).strip()
    if not re.match(r"^(?:SELECT|WITH)\b", code, flags=re.IGNORECASE):
        raise InputError("Oracle 连接为严格只读：仅允许 SELECT / WITH 查询")
    if ";" in code:
        raise InputError("Oracle 连接为严格只读：禁止多语句或分号 SQL")
    blocked = re.compile(
        r"\b(?:INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|RENAME|"
        r"GRANT|REVOKE|COMMIT|ROLLBACK|SAVEPOINT|LOCK|CALL|EXECUTE|EXEC|BEGIN|"
        r"DECLARE|SET|COMMENT|ANALYZE|AUDIT|NOAUDIT|FLASHBACK|PURGE)\b",
        flags=re.IGNORECASE,
    )
    match = blocked.search(code)
    if match:
        raise InputError(f"Oracle 连接为严格只读：禁止关键字 {match.group(0).upper()}")
    if re.search(r"\bFOR\s+UPDATE\b", code, flags=re.IGNORECASE):
        raise InputError("Oracle 连接为严格只读：禁止 SELECT FOR UPDATE")
    if re.search(r"\b(?:DBMS_|UTL_)\w*", code, flags=re.IGNORECASE):
        raise InputError("Oracle 连接为严格只读：禁止调用可能产生副作用的 Oracle 包")


def query_rmu_mapping(connection: Any, rmu_names: Sequence[str]) -> list[RmuMapping]:
    """Resolve selected devices, preferring exact ``id:<COMBINED_ID>`` tokens.

    Legacy plain RMU-name selectors remain supported for old bookmarks/reports.
    New browser selections always use COMBINED_ID so clicking one fuzzy-search
    candidate can never expand into every device that shares the same short
    RMU name.
    """

    selectors = [_clean_text(value) for value in rmu_names if _clean_text(value)]
    exact_ids = [value[3:] for value in selectors if value.lower().startswith("id:") and value[3:].strip()]
    legacy_names = [value for value in selectors if not value.lower().startswith(("id:", "fid:"))]
    rows: list[RmuMapping] = []

    def execute(sql: str, binds: Mapping[str, Any]) -> list[RmuMapping]:
        assert_oracle_read_only_sql(sql)
        cursor = connection.cursor()
        try:
            cursor.execute(sql, dict(binds))
            columns = [str(description[0]) for description in cursor.description]
            return [normalize_mapping(dict(zip(columns, row))) for row in cursor]
        finally:
            cursor.close()

    if exact_ids:
        sql, binds = build_rmu_id_sql(exact_ids)
        rows.extend(execute(sql, binds))
    if legacy_names:
        sql, binds = build_rmu_sql(legacy_names)
        rows.extend(execute(sql, binds))

    # Deduplicate and retain the operator's selection order.  FID tokens are a
    # JSON/offline fallback and are resolved from already returned rows only.
    by_selector = {_mapping_selector(item): item for item in rows}
    by_name: dict[str, list[RmuMapping]] = {}
    by_fid: dict[str, RmuMapping] = {}
    for item in rows:
        by_name.setdefault(_clean_text(item.rmu_name), []).append(item)
        if _clean_text(item.adms_gss_fid):
            by_fid[f"fid:{_clean_text(item.adms_gss_fid)}"] = item

    ordered: list[RmuMapping] = []
    seen: set[str] = set()
    for selector in selectors:
        item = by_selector.get(selector) or by_fid.get(selector)
        if item is not None:
            key = _mapping_selector(item)
            if key not in seen:
                ordered.append(item)
                seen.add(key)
            continue
        # Legacy selector: preserve all historical matches, but only new UI
        # selections use exact id: tokens.
        for legacy_item in by_name.get(selector, []):
            key = _mapping_selector(legacy_item)
            if key not in seen:
                ordered.append(legacy_item)
                seen.add(key)
    return ordered


def normalize_signal(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    point_type = _clean_text(_first(row, "point_type", "kind", "type", "signal_type"))
    raw_kind = point_type.upper()
    kind = {
        "STATUS INDICATION": "YX",
        "ANALOG MEASUREMENT": "YC",
        "COMMAND": "YK",
    }.get(raw_kind, raw_kind)
    if kind not in SUPPORTED_KINDS:
        raise InputError(
            f"第 {index} 个测点类型 {raw_kind!r} 不支持，支持：{', '.join(sorted(SUPPORTED_KINDS))}"
        )
    table = _clean_text(_first(row, "table", "table_no", "table_id", "protocol_table"))
    if not table:
        table = {"YX": "13560", "YC": "13561", "YK": "13579"}.get(kind, "")
    addr = _first(row, "addr", "address", "ioa", "point_address", "dot_no", default=None)
    if addr is None or _clean_text(addr) == "":
        raise InputError(f"第 {index} 个测点缺少 addr/address/ioa")
    try:
        address: int | str = int(addr)
    except (TypeError, ValueError):
        address = _clean_text(addr)
    # For the distribution SQL, SIGNAL_NAME is already generated by Oracle
    # according to the RMU/device/domain rules. Prefer it over any generic
    # description field so the report renders the database result verbatim.
    signal_name = _clean_text(_first(row, "signal_name", "desc", "description", "name", default=""))
    if not table and raw_kind in {"STATUS INDICATION", "ANALOG MEASUREMENT", "COMMAND"}:
        table = "三遥"
    direction = _clean_text(_first(row, "direction", default="")) or ("up" if kind in {"YX", "YC"} else "down")
    signal_id = _clean_text(_first(row, "id", "point_id", default=""))
    if not signal_id:
        combined_id = _first(row, "combined_id", "com_id", default="")
        prefix = _clean_text(combined_id) or table
        suffix = f":{address}" + (f":{kind}" if kind in {"YP", "PD", "SP"} else "")
        signal_id = f"{prefix}{suffix}" if prefix else f"{kind}{suffix}"
    return {
        "id": signal_id,
        "direction": direction,
        "table": table,
        "kind": kind,
        "desc": signal_name,
        "addr": address,
        "combined_id": _clean_text(_first(row, "combined_id", "com_id", default="")),
        "rmu_name": _clean_text(_first(row, "rmu_name", "RMU_NAME", default="")),
        "point_type": point_type,
        "table_no": table,
        "dot_no": address,
        "signal_name": signal_name,
        "station_id": _clean_text(_first(row, "station_id", "station", default="")),
        "pd_action": _first(row, "pd_action", "action", default=None),
        "device_type": _clean_text(_first(row, "device_type", "device", default="")),
        "selected": bool(_first(row, "selected", default=True)),
        "result": _clean_text(_first(row, "result", default="")),
        "received": _first(row, "received", default=""),
        "note": _clean_text(_first(row, "note", "remark", default="")),
    }


def normalize_signals(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        point = normalize_signal(row, index)
        if any(existing["id"] == point["id"] for existing in points):
            point["id"] = f"{point['id']}:{index}"
        points.append(point)
    return points


def _station_values(mapping: Sequence[RmuMapping]) -> tuple[str, str]:
    station = next((item.substation_name for item in mapping if item.substation_name), "")
    area = next((item.subcontrolarea_name for item in mapping if item.subcontrolarea_name), "")
    return station or "配网", area


def build_payload(
    mapping: Sequence[RmuMapping],
    points: Sequence[Mapping[str, Any]],
    *,
    report_id: str | None = None,
    protocol: str = DEFAULT_PROTOCOL,
    date_value: str | None = None,
) -> dict[str, Any]:
    station, area = _station_values(mapping)
    today = date_value or date.today().isoformat()
    normalized_points = normalize_signals(points)
    # Presentation metadata only: associate each returned point with its RMU by
    # COMBINED_ID so multi-RMU reports can render independent 3.x / 4.x groups.
    # This does not alter any Oracle SQL or query/filter behavior.
    mapping_by_combined_id = {
        _clean_text(item.combined_id): item
        for item in mapping
        if _clean_text(item.combined_id)
    }
    for point in normalized_points:
        mapped = mapping_by_combined_id.get(_clean_text(point.get("combined_id", "")))
        if mapped is not None:
            point["rmu_name"] = _clean_text(mapped.rmu_name)
            point["rmu_display_name"] = _clean_text(mapped.adms_gss_fid or mapped.rmu_name)
    table_counts: dict[str, int] = {}
    for point in normalized_points:
        table = point["table"] or "(未填写)"
        table_counts[table] = table_counts.get(table, 0) + 1
    channel_ip = next((item.ip for item in mapping if item.ip), "")
    resolved_protocol = next((item.protocol_name for item in mapping if item.protocol_name), protocol)
    channel_side = {
        "name": channel_ip, "port": "", "baud_rate": "", "data_bits": "",
        "parity": "", "stop_bits": "", "note": "",
    }
    # Each selected RMU has its own report number.  For a multi-RMU report,
    # keep the individual report numbers intact and separate them with " / "
    # instead of merging all RMU names into one long identifier.
    report_date = today.replace("-", "")
    report_ids: list[str] = []
    for item in mapping:
        identity = _clean_text(item.adms_gss_fid or item.rmu_name)
        identity = re.sub(r"[^0-9A-Za-z_-]+", "-", identity).strip("-")
        if identity:
            report_ids.append(f"E2E-{identity}-{report_date}")
    default_report_id = " / ".join(report_ids) if report_ids else f"E2E-{report_date}"
    return {
        "station": station,
        "st_id": area,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "counts": table_counts,
        "points": normalized_points,
        "distribution_mappings": [asdict(item) for item in mapping],
        "meta_defaults": {
            "report_id": report_id or default_report_id,
            "station": station, "st_id": area, "phase": "commission",
            "date_from": today, "date_to": today, "lead": "", "testers": "",
            "adms_version": "", "verdict": "", "verdict_conditions": "",
            "sign_role2": "se_scada",
            "channel": {"protocol": resolved_protocol, "primary": dict(channel_side), "backup": {"name": "", "port": "", "baud_rate": "", "data_bits": "", "parity": "", "stop_bits": "", "note": ""}},
        },
        "env_defaults": {f"E{index}": {"result": "", "note": ""} for index in range(1, 5)},
    }


def _render_mapping_section(mapping: Sequence[RmuMapping], rmu_names: Sequence[str] = ()) -> str:
    # Presentation only. RMU SQL/query logic is intentionally unchanged.
    headers = ["序号", "RMU名称", "RMU类型", "SMART", "NOP", "FUNCTION LOCATION", "IP", "规约", "总评", "操作"]
    en_headers = ["No.", "RMU Name", "RMU Type", "SMART", "NOP", "FUNCTION LOCATION", "IP", "Protocol", "Overall Result", "Action"]
    rows = []
    for index, item in enumerate(mapping, 1):
        rmu_key = _mapping_selector(item)
        legacy_rmu_key = _clean_text(item.rmu_name)
        cells = [str(index), item.adms_gss_fid or item.rmu_name, item.rmu_type, item.smart_type,
                 item.nop, item.function_location, item.ip, item.protocol_name]
        row_cells = "".join(f"<td>{html.escape(_clean_text(cell))}</td>" for cell in cells)
        verdict = (f'<td><select class="device-verdict compact" data-rmu="{html.escape(rmu_key, quote=True)}" data-rmu-legacy="{html.escape(legacy_rmu_key, quote=True)}">'
                   '<option value="">（未选）</option><option value="pass">通过</option>'
                   '<option value="conditional">Pass with comments</option><option value="fail">不通过</option>'
                   '</select></td>')
        remove_button = (f'<td><button type="button" class="rmu-remove-button compact" data-rmu="{html.escape(rmu_key, quote=True)}">'
                         '<span data-live-zh="">移除</span><span data-live-en="" style="display:none">Remove</span>'
                         '</button></td>')
        rows.append("<tr>" + row_cells + verdict + remove_button + "</tr>")
    body = "".join(rows) or '<tr><td colspan="10"><span data-live-zh="">未查询到匹配的环网柜</span><span data-live-en="" style="display:none">No matching RMU was found</span></td></tr>'
    head = "".join(f'<th><span data-live-zh="">{html.escape(zh)}</span><span data-live-en="" style="display:none">{html.escape(en)}</span></th>' for zh, en in zip(headers, en_headers))
    rmu_value = html.escape(",".join(rmu_names), quote=True)
    has_rmu_query = any(_clean_text(name) for name in rmu_names)
    database_result = ""
    if has_rmu_query:
        database_result = f'''\n    <div class="hint"><span data-live-zh="">已选设备：可继续模糊搜索追加环网柜，也可逐条移除；总评按设备分别填写。</span><span data-live-en="" style="display:none">Selected devices: continue fuzzy search to append RMUs, or remove them individually. Overall result is recorded per device.</span></div>\n    <div class="table-wrap"><table class="points" id="selected-rmu-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'''
    return f"""
  <section class="card no-print" id="distribution-rmu-map">
    <h2><span data-live-zh="">1. 配网设备查询</span><span data-live-en="" style="display:none">1. Distribution Device Search</span></h2>
    <form id="distribution-rmu-form" class="toolbar rmu-search-toolbar">
      <label class="field rmu-name-field" style="min-width:280px;flex:1">
        <span data-live-zh="">环网柜名称（RMU Name）</span><span data-live-en="" style="display:none">RMU Name</span>
        <input id="distribution-rmu-input" value="" data-selected-rmus="{rmu_value}" placeholder="例如：输入 346 后选择环网柜，可连续添加多个" autocomplete="off">
        <div id="rmu-suggestions" class="rmu-suggestions" hidden></div>
      </label>
      <button type="submit" class="rmu-search-button" aria-label="搜索数据库">
        <svg class="rmu-search-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.8" cy="10.8" r="6.8"></circle><path d="m16 16 5 5"></path></svg>
        <span class="rmu-search-label"><span data-live-zh="">搜索数据库</span><span data-live-en="" style="display:none">Search Database</span></span>
      </button>
      {('<span class="hint"><span data-live-zh="">数据库由服务端安全配置</span><span data-live-en="" style="display:none">Database is configured on the server</span></span>' if has_rmu_query else '')}
    </form>
    {database_result}
  </section>
"""


def _render_print_mapping_table(mapping: Sequence[RmuMapping]) -> str:
    headers = ["序号", "RMU名称", "RMU类型", "SMART", "NOP", "FUNCTION LOCATION", "IP", "规约", "总评"]
    en_headers = ["No.", "RMU Name", "RMU Type", "SMART", "NOP", "FUNCTION LOCATION", "IP", "Protocol", "Overall Result"]
    head = "".join(f'<th><span data-live-zh="">{html.escape(zh)}</span><span data-live-en="" style="display:none">{html.escape(en)}</span></th>' for zh, en in zip(headers, en_headers))
    rows = []
    for index, item in enumerate(mapping, 1):
        rmu_key = html.escape(_mapping_selector(item), quote=True)
        legacy_rmu_key = html.escape(_clean_text(item.rmu_name), quote=True)
        cells = [str(index), item.adms_gss_fid or item.rmu_name, item.rmu_type, item.smart_type,
                 item.nop, item.function_location, item.ip, item.protocol_name]
        row = "".join(f"<td>{html.escape(_clean_text(cell))}</td>" for cell in cells)
        row += f'<td class="print-device-verdict" data-rmu="{rmu_key}" data-rmu-legacy="{legacy_rmu_key}">—</td>'
        rows.append("<tr>" + row + "</tr>")
    body = "".join(rows) or '<tr><td colspan="9">—</td></tr>'
    colgroup = (
        '<colgroup>'
        '<col class="col-no">'
        '<col class="col-rmu">'
        '<col class="col-type">'
        '<col class="col-smart">'
        '<col class="col-nop">'
        '<col class="col-location">'
        '<col class="col-ip">'
        '<col class="col-protocol">'
        '<col class="col-verdict">'
        '</colgroup>'
    )
    return f'<div class="print-only" id="print-selected-rmu-wrap"><div class="table-wrap"><table class="points print-rmu-table" id="print-selected-rmu-table">{colgroup}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>'

def render_report_text(
    template: str,
    payload: Mapping[str, Any],
    *,
    include_mapping: bool = True,
    extra_after_main_start: str = "",
    extra_before_main_end: str = "",
    extra_before_body_end: str = "",
    print_password_hash: str = "",
    app_version: str = "unknown",
) -> str:
    """Render a template string without touching the filesystem."""

    # Header identity must be rendered server-side as well as patched by the
    # live browser script.  This prevents an early JavaScript error (or a stale
    # cached live script) from leaving the old Substation / Area subtitle on
    # screen.  VERSION is controlled by the application, but keep only safe
    # version-token characters before embedding it in JavaScript source.
    version_text = re.sub(r"[^0-9A-Za-z._+-]", "", _clean_text(app_version)) or "unknown"

    # Keep user/database text inside the JSON script element even if a
    # description happens to contain HTML-like characters.
    payload_json = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    pattern = r'(<script\s+id="payload"\s+type="application/json">).*?(</script>)'
    rendered, replacements = re.subn(
        pattern,
        lambda match: match.group(1) + payload_json + match.group(2),
        template,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if replacements != 1:
        raise InputError("模板中没有找到唯一的 payload JSON 节点")
    is_final_distribution_template = (
        'data-distribution-final-template="true"' in rendered
        or '<meta name="distribution-final-template" content="true">' in rendered
    )
    if print_password_hash:
        rendered, password_replacements = re.subn(
            r'(const\s+PRINT_PASSWORD_SHA256\s*=\s*)"[0-9a-fA-F]+"',
            lambda match: match.group(1) + json.dumps(print_password_hash),
            rendered,
            count=1,
        )
        if password_replacements != 1:
            raise InputError("模板中没有找到打印口令配置")
    mapping = [normalize_mapping(item) for item in payload.get("distribution_mappings", [])]
    if _clean_text(payload.get("network", "")) == "distribution":
        print_mapping = _render_print_mapping_table(mapping)
        rendered = rendered.replace('<h3 data-i18n="secChannel">', print_mapping + '<div class="screen-only distribution-channel-screen"><h3 data-i18n="secChannel">', 1)
        rendered = rendered.replace('</table>\n  </section>\n\n  <section class="card" id="stats">', '</table></div>\n  </section>\n\n  <section class="card" id="stats">', 1)
    if "<main>" not in rendered or "</main>" not in rendered:
        raise InputError("模板中没有找到 main 插入点")
    start_additions = extra_after_main_start
    if include_mapping and not is_final_distribution_template:
        start_additions += _render_mapping_section(mapping, payload.get("rmu_names", []))
    rendered = rendered.replace("<main>", "<main>" + start_additions, 1)
    additions = ""
    additions += extra_before_main_end
    rendered = rendered.replace("</main>", additions + "</main>", 1)
    station = html.escape(_clean_text(payload.get("station", "")))
    network = _clean_text(payload.get("network", ""))
    if network == "distribution":
        rendered = re.sub(
            r"<title>E2E Test Report — .*?</title>",
            f"<title>Distribution Equipment Signal E2E Test Report — {station}</title>",
            rendered,
            count=1,
        )
        distribution_protocol = _clean_text(
            payload.get("meta_defaults", {}).get("channel", {}).get("protocol")
        ) or "IEC 101"
        is_iec104 = "104" in distribution_protocol.upper().replace("-", "").replace(" ", "")
        # The supplied template is also used by the main-network report. For
        # distribution, replace the protocol and report identity before the
        # browser executes the template, so the page cannot briefly show or
        # persist main-network defaults.
        rendered = rendered.replace("IEC 101", distribution_protocol)
        distribution_labels = {
            'hdrTitle: "E2E 测试报告 · ADMS"': 'hdrTitle: "配网设备信号端到端测试报告 · ADMS"',
            'hdrSub: (s, id, t) => `站 ${s} · ${id} · 生成 ${t}`':
                f'hdrSub: (s, id, t) => `配网设备 · 版本 v{version_text} · 生成 ${{t}}`',
            'printTitle: "End-to-End Test Report（ADMS）"':
                'printTitle: "配网设备信号端到端测试报告"',
            'secEnv: "环境与前置条件"': 'secEnv: "配网设备环境与前置条件"',
            'secStats: "测试统计"': 'secStats: "RTU 信号测试统计"',
            'secPoints: "信号点表（全量 · 可检索勾选）"':
                'secPoints: "RTU 信号点表（全量 · 可检索勾选）"',
            'secPointsPrint: "测试明细（已勾选 / 已填结果）"':
                'secPointsPrint: "RTU 信号测试明细（已勾选 / 已填结果）"',
            'colDesc: "描述"': 'colDesc: "ADMS SIGNAL_NAME"',
            'hdrTitle: "E2E Test Report · ADMS"':
                'hdrTitle: "Distribution Equipment Signal End-to-End Test Report · ADMS"',
            'hdrSub: (s, id, t) => `Station ${s} · ${id} · Generated ${t}`':
                f'hdrSub: (s, id, t) => `Distribution Equipment · Version v{version_text} · Generated ${{t}}`',
            'printTitle: "End-to-End Test Report (ADMS)"':
                'printTitle: "Distribution Equipment Signal End-to-End Test Report"',
            'secEnv: "Environment & Preconditions"':
                'secEnv: "Distribution Equipment Environment and Preconditions"',
            'secStats: "Test Statistics"': 'secStats: "RTU Signal Test Statistics"',
            'secPoints: "Signal Point List (all · searchable and selectable)"':
                'secPoints: "RTU Signal Point List (all · searchable and selectable)"',
            'secPointsPrint: "Test Details (selected / with results)"':
                'secPointsPrint: "RTU Signal Test Details (selected / with results)"',
            'colDesc: "Description"': 'colDesc: "ADMS SIGNAL_NAME"',
            '<h1 id="hdr-title">E2E Test Report · ADMS</h1>':
                '<h1 id="hdr-title">Distribution Equipment Signal End-to-End Test Report · ADMS</h1>',
            '<h1 id="print-title">End-to-End Test Report (ADMS)</h1>':
                '<h1 id="print-title">Distribution Equipment Signal End-to-End Test Report</h1>',
        }
        if is_iec104:
            distribution_labels.update({
                'colPrimary: "主通道"': 'colPrimary: "通道"',
                'colPrimary: "Primary"': 'colPrimary: "Channel"',
            })
        for old, new in distribution_labels.items():
            rendered = rendered.replace(old, new)
        if is_iec104:
            # Distribution IEC-104 must show ONLY Protocol and Channel ID.
            # Sanitize the final channel table, not just the source template.
            # This also removes rows from older/custom templates where labels
            # or attributes differ but the input IDs are still present.
            channel_match = re.search(
                r'(<table[^>]*id=["\']channel-table["\'][^>]*>)(.*?)(</table>)',
                rendered, flags=re.DOTALL | re.IGNORECASE,
            )
            if channel_match:
                channel_html = channel_match.group(2)
                forbidden = (
                    'chPort', 'chNote', 'chBaud', 'chDataBits', 'chParity', 'chStopBits',
                    'ch-primary-port', 'ch-backup-port',
                    'ch-primary-note', 'ch-backup-note',
                    'ch-primary-baud_rate', 'ch-backup-baud_rate',
                    'ch-primary-data_bits', 'ch-backup-data_bits',
                    'ch-primary-parity', 'ch-backup-parity',
                    'ch-primary-stop_bits', 'ch-backup-stop_bits',
                )
                rows = re.findall(r'<tr\b.*?</tr>', channel_html, flags=re.DOTALL | re.IGNORECASE)
                for row in rows:
                    low = row.lower()
                    if any(token.lower() in low for token in forbidden):
                        channel_html = channel_html.replace(row, '')
                        continue
                    # Last-resort compatibility with very old Chinese/English templates.
                    plain = re.sub(r'<[^>]+>', ' ', row)
                    plain = re.sub(r'\s+', ' ', html.unescape(plain)).strip().lower()
                    if any(label in plain for label in ('tcp port', 'tcp 端口')) or plain in ('备注', 'note'):
                        channel_html = channel_html.replace(row, '')
                rendered = (
                    rendered[:channel_match.start(2)] + channel_html + rendered[channel_match.end(2):]
                )
        rendered = re.sub(
            r'\s*<h3 data-i18n="secEnvChecks">.*?</h3>\s*<table class="env-table">.*?</table>',
            '',
            rendered,
            count=1,
            flags=re.DOTALL,
        )
        rendered = re.sub(
            r'\s*<button[^>]*id="btn-sample20"[^>]*>.*?</button>',
            '',
            rendered,
            count=1,
            flags=re.DOTALL,
        )
        rmu_key = ",".join(_clean_text(name) for name in payload.get("rmu_names", [])) or "search"
        storage_key = json.dumps(f"distribution_rmu_e2e_report_{rmu_key}", ensure_ascii=False)
        rendered = re.sub(
            r'const STORAGE_KEY = .*?;',
            f"const STORAGE_KEY = {storage_key};",
            rendered,
            count=1,
        )
        if is_final_distribution_template:
            rendered, mapping_replacements = re.subn(
                r'<section class="card no-print" id="distribution-rmu-map">.*?</section>',
                _render_mapping_section(mapping, payload.get("rmu_names", [])),
                rendered,
                count=1,
                flags=re.DOTALL,
            )
            if mapping_replacements != 1:
                raise InputError("最终配网模板中没有找到环网柜查询区域")
    else:
        rendered = re.sub(
            r"<title>E2E Test Report — .*?</title>",
            f"<title>Distribution Signal Test Report — {station}</title>",
            rendered,
            count=1,
        )
    # The supplied template has these three values as static constants. Make
    # the scale hint and header match the distribution payload as well.
    js_station = json.dumps(_clean_text(payload.get("station", "")), ensure_ascii=False)
    js_area = json.dumps(_clean_text(payload.get("st_id", "")), ensure_ascii=False)
    js_generated = json.dumps(_clean_text(payload.get("generated_at", "")), ensure_ascii=False)
    js_counts = json.dumps(payload.get("counts", {}), ensure_ascii=False, indent=2)
    rendered = re.sub(r'const STATION = .*?;', f"const STATION = {js_station};", rendered, count=1)
    rendered = re.sub(r'const ST_ID = .*?;', f"const ST_ID = {js_area};", rendered, count=1)
    rendered = re.sub(r'const GENERATED_AT = .*?;', f"const GENERATED_AT = {js_generated};", rendered, count=1)
    rendered = re.sub(r'const COUNTS = \{.*?\n  \};', f"const COUNTS = {js_counts};", rendered, count=1, flags=re.DOTALL)
    if extra_before_body_end:
        if "</body>" not in rendered:
            raise InputError("模板中没有找到 </body> 插入点")
        if is_final_distribution_template:
            live_pattern = (
                r'<!-- distribution-live-script-start -->.*?'
                r'<!-- distribution-live-script-end -->'
            )
            rendered, live_replacements = re.subn(
                live_pattern,
                lambda _match: extra_before_body_end.strip(),
                rendered,
                count=1,
                flags=re.DOTALL,
            )
            if live_replacements == 0:
                rendered = rendered.replace("</body>", extra_before_body_end + "</body>", 1)
        else:
            rendered = rendered.replace("</body>", extra_before_body_end + "</body>", 1)
    return rendered


def render_report(
    template_path: Path,
    output_path: Path,
    payload: Mapping[str, Any],
    *,
    include_mapping: bool = True,
    extra_after_main_start: str = "",
    extra_before_main_end: str = "",
    extra_before_body_end: str = "",
) -> None:
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"无法读取报告模板：{template_path}\n{exc}") from exc
    rendered = render_report_text(
        template,
        payload,
        include_mapping=include_mapping,
        extra_after_main_start=extra_after_main_start,
        extra_before_main_end=extra_before_main_end,
        extra_before_body_end=extra_before_body_end,
    )
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        raise InputError(f"无法写入报告：{output_path}\n{exc}") from exc


def _query_from_environment(rmu_names: Sequence[str]) -> list[RmuMapping]:
    try:
        import oracledb  # type: ignore
    except ImportError as exc:
        raise InputError("实时查询需要安装 oracledb：pip install oracledb") from exc
    user, password, dsn = (os.environ.get(key) for key in ("ORACLE_USER", "ORACLE_PASSWORD", "ORACLE_DSN"))
    if not all((user, password, dsn)):
        raise InputError("实时查询需要 ORACLE_USER、ORACLE_PASSWORD、ORACLE_DSN")
    connection = oracledb.connect(user=user, password=password, dsn=dsn)
    try:
        return query_rmu_mapping(connection, rmu_names)
    finally:
        connection.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成配网 RMU 信号核验报告")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output", type=Path, default=Path("distribution_report.html"))
    parser.add_argument("--signals-json", type=Path, required=True, help="配网信号点 JSON")
    parser.add_argument("--mapping-json", type=Path, help="已查询好的 RMU 映射 JSON")
    parser.add_argument("--rmu", nargs="+", help="RMU 名称；与 Oracle 环境变量一起使用")
    parser.add_argument("--report-id")
    parser.add_argument("--protocol", default=DEFAULT_PROTOCOL)
    parser.add_argument("--date", dest="date_value")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.mapping_json and args.rmu:
        raise InputError("--mapping-json 和 --rmu 二选一")
    if not args.mapping_json and not args.rmu:
        raise InputError("请提供 --mapping-json，或提供 --rmu 并配置 Oracle 环境变量")
    mappings = (
        [normalize_mapping(row) for row in load_json_rows(args.mapping_json)]
        if args.mapping_json
        else _query_from_environment(args.rmu)
    )
    payload = build_payload(
        mappings,
        load_json_rows(args.signals_json),
        report_id=args.report_id,
        protocol=args.protocol,
        date_value=args.date_value,
    )
    render_report(args.template, args.output, payload)
    print(f"已生成：{args.output.resolve()}")
    print(f"RMU：{len(mappings)}；测点：{len(payload['points'])}；表：{payload['counts']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as exc:
        raise SystemExit(f"错误：{exc}")
