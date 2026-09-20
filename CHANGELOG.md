## 1.2.9

- Restored the original three-remote source table numbers in the point list: YX=13560, YC=13561, YK=13579, replacing the generic `三遥` display.
- Removed the standalone `PD` column from the signal-points table.
- Kept the v1.2.8 match-key rules and all unrelated behavior unchanged.

## 1.2.8

- Point-table SQL updated to the latest supplied COM_ID query: YX/YC use `reference_name` as the match key, YK uses `index_no`, while the original point number is retained as `no`.
- No unrelated UI, RMU search, protocol/channel, configuration, or report-layout changes.

## 1.2.7
- Formally supports alphanumeric RMU names containing hyphens, such as `F05-1509`, across partial search, exact selection, URL navigation, and Oracle bind queries.
- Added regression coverage for `F05`, `1509`, and `F05-1509`.

## 1.2.6

- Renamed the report-facing RMU RTU title to the more general Distribution Equipment wording in both live and print/PDF views.
- Kept RMU-specific search and RTU signal terminology where it describes the actual current workflow/data.

## 1.2.5

- PDF/print report footer now contains only centered page numbering (`1 / 5`).
- Removed report footer date/time and the `Page` prefix.
- Kept the v1.2.4 IEC-104 single-channel display fix.

# v1.2.4

- IEC-104 print summary now shows only actual channel/IP data.
- Removed serial framing text such as 9600-8-E-1 from IEC-104 summary.
- A single IEC-104 channel is no longer duplicated as Primary/Backup.

# v1.2.3
- Unified runtime and release configuration on `report_config.json`.
- Default server port is 8899 in source and release builds.
- Default Print/PDF password is `NARI`.
- Oracle settings are read from `config/report_config.json` in source mode and EXE-adjacent `report_config.json` in packaged mode.
- Release build copies the canonical config instead of rebuilding a different configuration.

## v1.2.2
- Default web port changed from 8787 to 8899 to avoid accidentally connecting to an older service instance.
- `startreport.cmd` / launcher / live server defaults are aligned to port 8899.

# v1.2.0

- Completed RMU partial-search + selectable candidate workflow.
- Search `346` uses Oracle substring matching on `dms_combined_device.name` and returns matching RMUs.
- Search API now returns explicit JSON errors and the page displays search failures instead of silently hiding them.
- Candidate selection opens the full real-time report only after a concrete RMU is selected.

# v1.1.8

- Fixed the actual runtime template: removed stale embedded live-script from web/distribution_report.html.
- IEC-104 Environment Precautions source HTML contains only Protocol and Channel ID.
- RMU partial search is injected once at runtime and calls /api/rmu-search?q=<keyword>; candidate selection opens the full report.
- Added regression tests against the final rendered HTML.

# Changelog

## v1.1.7 - 2026-09-19
- IEC-104 Environment Precautions now renders only Protocol and Channel ID; TCP Port, Note, baud rate, data bits, parity and stop bits are removed from the actual distribution template and final renderer.
- RMU search uses partial-name matching and returns selectable candidates before opening the report.
- Added regression tests for IEC-104 environment rows, partial RMU SQL, candidate search payload and search API behavior.

# v1.1.6

- Removed TCP Port and Note from the actual runtime distribution HTML template.
- Replaced the stale embedded RMU search script with the current fuzzy-search + candidate-selection implementation.
- RMU partial text such as `346` now queries `/api/rmu-search` and displays selectable candidates before loading a report.

## v1.1.5
- Fixed RMU fuzzy-search API SQL and candidate selector rendering.
- RMU search now returns substring matches such as 346 -> 34661 for user selection.
- Removed TCP Port and Note rows directly from generated distribution IEC-104 HTML.

# Changelog

## V1.1.4

- RMU search now supports partial-name lookup and a selectable suggestion list.
- Removed TCP Port and Note rows from the IEC-104 distribution channel section.
- Kept exact RMU loading after a candidate is selected.

## V1.1.3

- Fixed nonexistent RMU searches being reported as HTTP 500 / server processing failures.
- A nonexistent RMU now renders the normal report page with "未查询到匹配的环网柜 / No matching RMU was found".
- Added defensive handling for RMU mappings without COM_ID so empty COM_ID lists are not passed to protocol/point SQL builders.
- Kept Oracle failures and unexpected server exceptions as real HTTP 500 errors.

## V1.1.2

- Fixed packaged EXE failure `DPY-3016` caused by missing `cryptography`.
- Release build now explicitly collects `cryptography`, its Rust bindings, and `cffi`.
- Added runtime dependency preflight before PyInstaller packaging.
- HTTP request boundary now returns a controlled 500 response instead of closing the socket and causing `ERR_EMPTY_RESPONSE`.
- Kept the validated RMU/point-table SQL and report business logic unchanged.

## V1.1.1
- Fixed release configuration generation when JSON properties are absent.
- Generate `report_config.json` from a complete schema instead of mutating an example object.
- Write release JSON as UTF-8 without BOM and validate it before packaging.
- Keep PyInstaller `getpass` and complete `oracledb` collection for standalone Oracle access.
- Fail the release build if the executable, configuration, or ZIP is missing/invalid.
- Keep the final operator package minimal: EXE, configuration, version, README, and logs directory.

## V1.1.0
- Reorganized the repository into src/web/config/scripts/examples/docs/tests structure.