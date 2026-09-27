# v1.2.62 - 2026-09-27

- Fixed EN -> add device -> Chinese fallback by making the selected language navigation-durable in the same browser tab.
- Added a single global controller that mirrors the operator-selected value into `window.name`, a same-origin cookie, and `localStorage`; `window.name` is authoritative during same-tab full-page navigation.
- Only explicit 中文 / EN clicks can choose a new language. Device add/remove, report restore, History -> Continue Test, Dashboard/Home navigation, and RMU state handoff cannot switch it.
- Oracle SQL, device-search SQL, exact-device selection, duplicate-name handling, and read-only protections are unchanged.

# v1.2.60 - 2026-09-27

- Fixed repeated device navigation falling back from English to Chinese.
- Added a one-time same-tab navigation language lock that only mirrors the language already active before navigation.
- Only manual `中文 / EN` clicks choose a language; no other operation can switch it.
- History -> Continue Test, Home, Dashboard, History, refresh/back/forward, and repeated device add/remove preserve the current language.
- Oracle/query logic is unchanged and remains read-only.

# v1.2.59 - 2026-09-27

- Fixed History -> Continue Test switching back to the language stored with an older task.
- The operator-selected language is now controlled only by the explicit 中文 / EN buttons.
- `localStorage` is the sole language authority across ETE Test, History, and Test Overview; legacy session/navigation language handoffs are ignored.
- Saved report JSON and add/remove-device state handoffs are language-neutral and cannot change the UI language.
- No Oracle SQL, device-search SQL, selector/query behavior, duplicate-name handling, or read-only enforcement changed.

# v1.2.58 - 2026-09-27

- Fix: the operator-selected UI language now survives the full-page navigation used when adding/removing a distribution device.
- EN remains EN and Chinese remains Chinese unless the operator explicitly clicks the other language button.
- Added a one-time browser-only language navigation handoff; it does not change Oracle SQL, search SQL, selector tokens, or query parameters.
- History/server draft restore still cannot override the operator's current language.

# v1.2.57

- Fixed language divergence between ETE Test, History, and Test Overview.
- `localStorage` is now the single authoritative language preference across pages and browser tabs; stale tab-scoped state can no longer override it.
- Normal test operations (editing points, adding/removing devices, saving progress) no longer write the language preference. Only an explicit 中文 / EN click changes the language.
- Open tabs synchronize an explicit language change through the browser storage event.
- No Oracle SQL, device search SQL, read-only guard, or device-selection/query behavior was changed.

# v1.2.56 - 2026-09-27

- Enforced one-language-at-a-time rendering across the complete UI: EN mode shows English application labels/messages/results only; 中文 mode shows Chinese application labels/messages/results only.
- Fixed remaining mixed-language result/kind labels in the main test page and synchronized live device-search UI with the same language source of truth.
- History and Dashboard keep the selected language; Dashboard export HTML/PDF now uses the language active when the export is created.
- Server/API error details are kept in logs while the browser shows only localized user-facing messages, preventing wrong-language raw errors from leaking into the UI.
- User-entered text and technical/database identifiers are never translated.
- Oracle SQL, device-search SQL, exact mouse-selected device logic, duplicate-name handling, and read-only enforcement are unchanged.

# v1.2.55 - 2026-09-27

- Fixed mixed Chinese/English rendering on the main ETE page when the operator is already in EN mode.
- The server-rendered Distribution Device Search block now follows the same `lang` source of truth as the rest of the page, including Device Name/Device Type headings, search labels/hints, Remove, and Overall Result option labels.
- EN remains EN across device search/add/remove/reload until the operator explicitly clicks 中文; Chinese behaves symmetrically.
- This release is frontend-only for the fix: Oracle SQL, device-search SQL, query selection logic, and read-only enforcement are unchanged.

# v1.2.54 - 2026-09-27

- Fix language persistence across device add/remove full-page reloads.
- When the operator selects EN, the test page remains English until 中文 is explicitly selected (and vice versa).
- Language preference is stored independently in both localStorage and sessionStorage; restoring drafts/handoffs never changes it.
- No Oracle SQL, device-search SQL, RMU selection query, or database read-only rules were changed in this release.

# v1.2.53 - 2026-09-27

- Rebuilt directly from the user-verified v1.2.47 source baseline where device fuzzy search is confirmed working.
- Preserved the working canonical local Oracle runtime configuration instead of replacing it with an empty configuration during the source upgrade.
- Kept the proven read-only Oracle search path and exact mouse-selected device handling, including duplicate short device names.
- Re-applied the later requirements: Device Name / Device Type terminology, bilingual Overall Result options, bilingual History/Dashboard, and sticky 中文 / EN preference.
- Oracle remains strictly read-only.

# v1.2.47 - 2026-09-27

- 修复“保存草稿 -> 历史报表 -> 继续测试”后重复短名称设备被再次展开的问题。
- 根因：历史页此前用 `rmu_name`（如 `6`）重新构造继续测试 URL，导致 Oracle 兼容旧逻辑按短名称匹配，把多个不同馈线但同名为 `6` 的设备一起加载。
- 继续测试现在优先使用历史记录中的完整 `ADMS_GSS_FID`，生成 `fid:<完整设备名>` 精确选择器；仅对真正的旧记录保留短名称兼容。
- 若旧历史记录缺少完整 display_name，但仍保留区域/变电站/馈线/RMU 层级，会用这些字段重建完整 FID 后精确恢复。
- 修复历史归档中每台设备“总评”的键匹配：优先按完整 FID / COMBINED_ID，再兼容旧短名称，避免多个同名 RMU 共用或丢失总评。
- Oracle 行为不变，仍严格只读，仅允许 SELECT/WITH SELECT。

# v1.2.46 - 2026-09-27

- 修复新增第二个配网设备后，已在第一个设备填写的测试结果看起来被清空/分组为 0 的问题。
- 根因之一是多设备页面的分组仍优先使用 `COMBINED_ID`；当 Oracle ID 超过 JavaScript 安全整数范围时，映射 ID 与点表中的字符串 ID 可能不一致。现在屏幕端多设备分组统一优先使用鼠标选中的完整 `ADMS_GSS_FID`。
- `distribution_mappings[].combined_id` 在浏览器 payload 中强制转换为字符串，彻底避免 JSON/JavaScript 大整数精度损失。
- 新增稳定的点状态键：`完整设备 FID + 点类型 + 表号 + 地址`。新增/删除设备发生整页重载时，除旧的 point id 外还会用稳定键恢复原设备的勾选、是否收到、Pass/Fail 和备注。
- 新增设备只初始化新增设备自己的点，不重置已有设备已经填写的测试状态。
- Oracle 行为不变，仍严格只读，仅允许 SELECT/WITH SELECT。

# v1.2.45 - 2026-09-27

- 修复模糊搜索后点击某一设备却可能加载到其他设备的问题。
- 浏览器选择设备时以鼠标点击的完整 `ADMS_GSS_FID` 为唯一选择依据，不再优先使用 `COMBINED_ID`。
- 新增按完整 `ADMS_GSS_FID` 精确只读查询 Oracle 的路径；最后一段仍对应实际 RMU 名称/编号，但不会仅凭重复的短编号做模糊扩展。
- 保留旧版 `id:<COMBINED_ID>` 选择器兼容，历史链接/草稿仍可继续使用。
- 搜索 API 中 `COMBINED_ID` 强制序列化为字符串，避免浏览器大整数精度问题。
- Oracle 仍严格只读，仅允许 SELECT/WITH SELECT。

# v1.2.44 - 2026-09-27

- Fixed fuzzy RMU selection so clicking one search result adds **only the exact device that was clicked**, even when several feeders contain the same short RMU name (for example `6`).
- Search results now carry the device `COMBINED_ID`; selected devices are represented by stable `id:<COMBINED_ID>` tokens instead of ambiguous short RMU names.
- Added an exact, read-only Oracle mapping query by `COMBINED_ID`. Fuzzy matching remains only in the search candidate list; after selection there is no fuzzy expansion.
- Remove now targets the exact selected device, so removing one duplicated short-name RMU does not remove or affect another.
- Multi-device point grouping and per-device overall-result keys now use unique device identity, preventing duplicated short RMU names from sharing statistics or verdict state.
- Kept backward compatibility for legacy plain-RMU-name report URLs and migrated older per-device verdict keys when possible.
- Oracle access remains strictly read-only; this change adds only SELECT-based lookup logic.
- Automated regression suite: 130 tests passed.

# v1.2.43 - 2026-09-27

- Removed the 60-second full-page auto-refresh from the ETE testing page.
- A running test session now stays on the current browser state until the operator explicitly navigates, searches, saves, resets, or refreshes the page.
- Continuing a saved report restores the server draft only on explicit entry/navigation instead of reloading it every minute.
- Kept the existing refresh configuration parameter for backward compatibility, but it no longer triggers browser page reloads.
- Oracle access remains strict read-only.

# v1.2.42 - 2026-09-27

- Renamed the main section title from `配网环网柜查询 / Distribution RMU Search` to `配网设备查询 / Distribution Device Search` so the page title matches the broader distribution-device test scope.
- Kept the current `环网柜名称（RMU Name）` input label and RMU search behavior unchanged; this release changes the section title only.
- No Oracle SQL, report state, PDF, history, or test-progress logic changes. Oracle remains strictly read-only.

# v1.2.41 - 2026-09-27

- Fixed multi-RMU incremental testing: adding or removing an RMU no longer resets test progress already entered for the existing selected RMUs.
- Root cause: RMU selection intentionally performs a full page navigation so the new device point list can be read from Oracle; the previous in-memory report state was not carried across that navigation, so the page rebuilt every selected device from fresh query results.
- Added a one-time same-tab `sessionStorage` handoff for RMU add/remove navigation. It carries the current report state, report UUID and small UI context into the newly rendered multi-RMU page, restores matching existing point IDs, leaves newly added RMU points blank, then immediately deletes the handoff token/data. A normal page open still starts clean.
- No automatic persistent browser test-state cache was reintroduced. History -> Continue Test remains the only normal server-side draft restoration path.
- Oracle behavior is unchanged and remains strictly read-only; adding an RMU performs query-only Oracle access and never writes Oracle data.

# v1.2.40 - 2026-09-27

- Fixed per-RMU overall-result propagation into print/PDF output.
- Root cause: the editable RMU selector lives in the live-script scope while the report `state` is private to the main report IIFE; v1.2.39 attempted to read a global `state` that does not exist, so the selected verdict was never written into the archived report state.
- Added an explicit `window.getDeviceVerdicts` / `window.setDeviceVerdict` bridge owned by the main report so screen selection, archive snapshot, history resume and print/PDF all use the same `meta.device_verdicts` object.
- Existing Oracle access remains strictly read-only. No Oracle write path was added.

# v1.2.39 - 2026-09-27

- Fixed per-RMU `总评 / Overall Result` missing from browser print preview and archived HTML/PDF even when the screen selector already showed `通过 / Pass`.
- The print-only RMU table is now synchronized from `meta.device_verdicts` immediately before `beforeprint` rendering and before the frozen archive HTML is cloned.
- History -> Continue Test now refreshes the per-RMU verdict selectors after asynchronous saved-state restoration.
- Made the per-RMU verdict binding idempotent so re-syncing does not add duplicate change listeners.
- No Oracle SQL/query behavior changed; Oracle remains strictly read-only.

# v1.2.38 - 2026-09-27

- Fixed the empty Test Dashboard on first open: `/dashboard` now auto-loads the existing server-side ETE history immediately.
- Added a local-history dashboard mode that does **not** query Oracle when area/substation/feeder are blank. Existing tested/in-progress devices, Pass/Pass with comments/Fail counts, feeder breakdown and report links are shown from the local archive.
- In local-history mode, `未调试` and `完成率` are shown as unknown (`—`) instead of misleading zero/100% values because no authoritative device population has been queried.
- Entering an area, substation, or feeder switches to the existing device-coverage mode: SMART inventory is read and merged with local report history to calculate total/untested/completion. Oracle access remains strictly read-only.
- Date-only filtering stays in local-history mode and does not trigger an Oracle inventory query.
- Updated overall-summary HTML/PDF labels so history-only exports distinguish `历史测试设备` from scoped `智能设备总数`.
- Kept the existing draft/final workflow unchanged: Save Current Report remains `草稿 / 未完成`; the existing formal Print/PDF flow promotes the report to `正式 / 已完成`.

# v1.2.37 - 2026-09-26

- Swapped the header positions of `首页 / Home` and the `中文 / EN` language switcher. The new order starts with Home, then the language switcher, followed by Reset/Save/Dashboard/History/Print actions.
- No Oracle query, read-only guard, report data, history, PDF, or test-state logic changes.

# v1.2.36 - 2026-09-26

- Enforced strict Oracle read-only SQL validation on every Oracle execution path: only one `SELECT` / `WITH ... SELECT` statement is accepted; DML, DDL, PL/SQL, transaction-control statements and `SELECT FOR UPDATE` are rejected before cursor execution.
- Removed browser persistence/automatic restoration of test state. `localStorage` now retains language preference only; test selections, results, received flags, notes and report metadata are never restored on a normal reopen.
- Removed automatic `sessionStorage` report UUID reuse. Only an explicit History -> Continue Test link (`?resume=<uuid>`) restores a saved draft.
- Added `首页 / Home` and `重置当前测试 / Reset Current Test` actions. Reset clears only the current client test state and never deletes saved history.
- Kept local SQLite/JSON/PDF report archiving writable; this is separate from Oracle and does not write to Oracle.

## v1.2.35

- 历史报表页新增“生成 PDF / 重新生成 PDF”，草稿、未完成、正式、已完成状态均可生成当前已保存快照的 PDF。
- PDF 生成与测试状态解耦：生成或重新生成 PDF 不会把草稿自动改为正式，也不会修改最后保存时间。
- 草稿 PDF 自动保留 `DRAFT / 非最终版本` 水印；正式报告 PDF 不显示草稿水印。
- PDF 从服务端已归档 HTML 快照生成，不重新查询 Oracle，避免历史测试结果被后续实时数据改变。
- 已生成后提供“查看 PDF / 下载 PDF / 重新生成 PDF”；生成失败时保留原有 PDF。
- 不修改 RMU 查询、点表 SQL、Oracle 查询、配置文件或 `scripts/run.ps1`。

## v1.2.34

- Removed the `ADMS 版本 / ADMS Version` row from the PDF/print cover metadata.
- The editable `主站 / 前置版本 (ADMS / FES Version)` field and archived report data remain unchanged; this change only affects PDF/print cover presentation.
- No RMU query, point SQL, Oracle query, report archive schema, runtime config, or `scripts/run.ps1` changes.

## v1.2.33

- 修复运行时页头仍显示“变电站 / 区域”的问题。
- 页头副标题现在由服务端直接渲染为“配网设备 · 版本 v1.2.33 · 生成 …”，不再依赖后置浏览器脚本才能覆盖。
- 英文页头对应显示“Distribution Equipment · Version v1.2.33 · Generated …”。
- 不修改 RMU 查询、点表 SQL、Oracle 查询、配置文件或 run.ps1。

## v1.2.32

- Simplified the main ETE page header subtitle: removed Substation/Area and added the running application version.
- Chinese header now shows `配网设备 · 版本 vX.Y.Z · 生成 ...`; English shows `Distribution Equipment · Version vX.Y.Z · Generated ...`.
- No RMU/point/protocol SQL, Oracle query, runtime config, or `scripts/run.ps1` changes.

## v1.2.31

- Added a centralized `/dashboard` management page for area/substation/feeder ETE progress.
- Added a separate SMART-device inventory query for dashboard population counts without changing the existing RMU search, exact RMU query, point SQL, protocol SQL, or Oracle point-loading workflow.
- Dashboard merges current SMART-device inventory with the latest finalized ETE result per device and shows total/tested/in-progress/untested, Pass/Pass with comments/Fail, completion rate and pass rate.
- Added per-feeder progress statistics and device-level drill-down links to archived reports.
- Added persistent SMART-device inventory cache in SQLite and fallback to the latest cache when Oracle inventory lookup fails.
- Added overall summary report export with persistent HTML/JSON/PDF snapshots under `data/summary_reports/`.
- Added schema migration v3 for inventory cache and summary-report metadata; existing report history is preserved.
- Added Dashboard navigation from ETE Test and History pages.
- `config/report_config.json` and `scripts/run.ps1` remain unchanged.

## v1.2.30

- Replaced the top-level `保存 JSON / 加载 JSON` workflow with `保存当前报告`.
- The current ETE test can be saved to the central service at any time as a draft. Repeated saves update the same draft instead of creating duplicate history rows.
- Historical reports now distinguish `草稿 / 未完成` and `正式 / 已完成`; drafts include a `继续测试` action that restores the saved test state.
- Formal `打印 / PDF` promotes the current draft to the final report using the same report UUID and then opens the local print dialog.
- Added schema migration v2 (`updated_at`, `finalized_at`, status indexes) while preserving existing v1.2.29 report data.
- Draft saves archive JSON/HTML only; final Print/PDF generates the server-side PDF.
- Existing RMU search SQL, point SQL, Oracle query logic, `scripts/run.ps1`, and `config/report_config.json` remain unchanged.

## v1.2.29

- Renamed the delivery/project package identity to `distribution-ete-test-report`.
- Formal Print/PDF now archives the current frozen report to the central service before opening the local print dialog.
- Added persistent storage under the program directory: `data/database`, `data/reports`, and `data/backup`.
- Added SQLite WAL-based report metadata storage with schema migration tracking and automatic pre-migration database backups.
- Added historical report page `/history` with filters for debug/test date, substation, feeder, device, test lead and verdict.
- Added report view/download endpoints for PDF, HTML and JSON snapshots.
- Server-side PDF archive uses local Edge/Chrome/Chromium headless printing when available; HTML and JSON are always archived.
- Existing RMU search SQL, point SQL, Oracle query logic, `scripts/run.ps1`, and `config/report_config.json` are unchanged.

## v1.2.28

- PDF 报告中的“RTU 信号测试统计”改为第一种汇总表形式：一个表头，按每个选中设备一行展示。
- 列包含：设备、计划、已测、上行覆盖、下行覆盖、Pass、Pass with comments、Fail、Blocked、N/A、Pass率。
- 网页端 3.x 统计卡片保持原样，仅调整 PDF / 打印布局。
- 不修改 RMU 查询逻辑、点表 SQL、Oracle 查询逻辑、配置文件与运行脚本。

## v1.2.27

- Multi-RMU report numbers are now generated per device and separated with ` / ` on the signature page.
- Example: `E2E-RMU-A-20260926 / E2E-RMU-B-20260926`.
- No RMU search SQL, point SQL, Oracle query logic, run script, or site config changes.

## v1.2.26

- Removed the substation row from the PDF/print signature-page metadata.
- Kept report number and test date unchanged.

## v1.2.25

- PDF：RTU 信号测试统计改为紧凑表格展示；网页统计卡片保持不变。
- 不修改 RMU 查询、模糊搜索、点表 SQL 或 Oracle 查询逻辑。
- `config/report_config.json` 保持原样。

# Changelog

## 1.2.23
- 优化正式打印/PDF中的多 RMU 设备表列宽与打印字体，避免表头和单元格重叠。
- 报告封面移除单一 IEC-104 通道摘要，多 RMU 通道信息统一保留在设备表中。
- 不修改 RMU 查询、模糊搜索、点表 SQL 或 Oracle 查询逻辑。

## 1.2.22 - 2026-09-26

- Based strictly on the supplied v1.2.13 source layout and existing query logic.
- Added multi-RMU selection by repeated fuzzy search, per-RMU overall result, and per-row remove action.
- Added per-RMU 3.x statistics and full-height 4.x signal point groups without changing the existing RMU/point SQL.
- Simplified the report cover by removing report number, substation, region, and global overall result.
- The web-only environment block is hidden; the print/PDF environment section lists the selected RMUs.
- No server-side report archive/history feature is included.

## 1.2.13 - 2026-09-25

- Fixed `scripts/build_release.ps1` aborting with `NativeCommandError` when PyInstaller is absent from a newly-created virtual environment.
- PyInstaller availability is now checked with `importlib.util.find_spec()` without importing the package; the build script installs PyInstaller automatically when missing.
- Continues to invoke PyInstaller as `python -m PyInstaller` for Windows App Control compatibility.

# Changelog

## 1.2.12

- Replaced the live RMU identity query with the newly supplied RMU-name SQL, including `dms_combined_device.st_string_07` as `FUNCTION LOCATION`.
- Added `FUNCTION LOCATION` to the RMU result table immediately before `IP`.
- Preserved the existing point-table SQL, IEC-104 display, report workflow, and Windows build behavior.

## 1.2.11

- Fixed Windows release builds on managed endpoints where `pyinstaller.exe` is blocked by application control.
- `build_release.ps1` now invokes PyInstaller via the active project Python: `python -m PyInstaller`.
- PyInstaller is installed only when its Python module is missing, avoiding unnecessary reinstall on every build.

## 1.2.10

- Replaced the COM_ID point-table query with the newly supplied SQL.
- YX/YC use `reference_name`, YK uses `index_no`, and rows with null or `-1` match keys are filtered exactly as supplied.
- Preserved the report-facing source table labels YX=13560, YC=13561, YK=13579 without changing the supplied Oracle query output.
- No unrelated RMU search, protocol/channel, configuration, or report-layout changes.

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

## 1.2.12

- Replaced the live RMU identity query with the newly supplied RMU-name SQL, including `dms_combined_device.st_string_07` as `FUNCTION LOCATION`.
- Added `FUNCTION LOCATION` to the RMU result table immediately before `IP`.
- Preserved the existing point-table SQL, IEC-104 display, report workflow, and Windows build behavior.

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

## 1.2.12

- Replaced the live RMU identity query with the newly supplied RMU-name SQL, including `dms_combined_device.st_string_07` as `FUNCTION LOCATION`.
- Added `FUNCTION LOCATION` to the RMU result table immediately before `IP`.
- Preserved the existing point-table SQL, IEC-104 display, report workflow, and Windows build behavior.

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

## 1.2.24
- Restore `config/report_config.json` and `config/report_config.example.json` exactly from the user-provided v1.2.13 baseline.
- Keep `scripts/run.ps1` config-loading behavior unchanged.
- No SQL/query logic changes.
