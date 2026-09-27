# Distribution ETE Test Report

V1.2.62

## v1.2.62 navigation-durable global language controller

- Keeps one operator-selected language across the whole application.
- The current same-tab language is mirrored in `window.name`, a same-origin cookie, and the existing `localStorage` key so a full-page add/remove-device navigation cannot fall back to Chinese if browser storage is unavailable or stale.
- Only explicit 中文 / EN clicks may choose a new language; report restore, device add/remove, History -> Continue Test, Dashboard/Home navigation, and RMU handoff are language-neutral.
- The three pages (ETE Test, History, Test Overview) use the same controller and preference.
- Oracle SQL, device-search SQL, exact-device selection, duplicate-name handling, and read-only query behavior are unchanged.

## v1.2.60 navigation language lock

- Only the explicit `中文 / EN` controls choose a language.
- A one-time same-tab navigation lock now carries the already-active language across every full-page reload.
- Repeated device additions/removals, History -> Continue Test, Home, Dashboard, History, refresh, back and forward all preserve the current language.
- Oracle SQL, device-search SQL, exact-device selection, and read-only protection are unchanged.

## v1.2.59 operator-only global language authority

The current UI language is now controlled **only** by the explicit 中文 / EN buttons. The language selected by the operator is stored in one application-wide `localStorage` key and is shared by the ETE Test, History, and Test Overview pages. Saved reports, server draft restore, History -> Continue Test, add/remove-device handoffs, and ordinary navigation can no longer override it.

This release intentionally does **not** change Oracle SQL, device-search SQL, exact mouse-selected device behavior, duplicate-name handling, or read-only enforcement.

## Version
V1.2.62

## v1.2.57 strict single-language UI

The operator-selected language is now enforced across the whole workflow. In **EN** mode, all application UI labels, status/result text, live device-search messages, History/Dashboard messages, and exported Dashboard summary reports render in English; in **中文** mode the same UI renders in Chinese. User-entered comments, database device names, signal names, protocol names, file-format names, and organization/product acronyms remain unchanged as data/technical identifiers. The language never changes unless the operator explicitly presses 中文 or EN.

This release is presentation/i18n-only. Oracle remains strictly read-only, and the proven device search SQL, exact mouse-selected device logic, duplicate-name handling, and query path are unchanged.

## v1.2.55 unified language rendering

The main report and the server-rendered Distribution Device Search block now use the same language state. If EN is selected, all live device-search labels, selected-device table headings, verdict choices, hints and Remove actions remain English through device add/remove/reload until 中文 is explicitly selected. This UI-only fix does not change Oracle SQL or query behavior.



## v1.2.54 sticky language preference

Selecting **EN** or **中文** is now a persistent operator UI preference. Adding/removing a distribution device causes a full-page reload, but it no longer resets the page language. This release intentionally does **not** change Oracle SQL or the device-search/query path.

## v1.2.53 working-search rebase

This release is rebuilt from the user-verified **v1.2.47 working device-search baseline**. The proven Oracle read-only search/selection path and the existing canonical local `config/report_config.json` are preserved. Later UI requirements are layered on top: bilingual History/Dashboard, Device Name/Device Type wording, bilingual Overall Result options, and sticky language preference.

The source package deliberately keeps the local canonical runtime configuration from the working baseline; `.gitignore` continues to exclude `config/report_config.json` so it is not intended for repository commits.


## Exact device selection

The RMU search box remains a fuzzy Oracle read-only lookup, but clicking a search candidate now selects that exact database device by its unique `COMBINED_ID`. A short RMU name such as `6` may exist on multiple feeders; selecting one candidate adds only that candidate, and each Remove action removes only that selected device. Multi-device statistics, point groups, per-device overall results, save/resume and print/PDF grouping also use the unique device identity so duplicate short RMU names do not collide. Legacy report URLs that contain plain RMU names remain readable for backward compatibility.

## Central report archive

Use **保存当前报告 / Save Current Report** at any time to save or update the current server-side draft. Browser localStorage never stores test selections, Pass/Fail results, received flags, notes, or report metadata; a normal reopen always starts clean. When an operator adds/removes an RMU during the same open test, v1.2.41 uses a one-time same-tab `sessionStorage` handoff so already-entered results are preserved across the required page navigation; the handoff is deleted immediately after it is consumed and is not a normal reopen/restore mechanism. Only **历史报表 -> 继续测试** explicitly restores a server-side draft. Formal Print/PDF promotes that same draft to the final archived report before the local print dialog opens. Persistent data is stored below `data/` in the program directory:

- `data/database/ete_reports.db`
- `data/reports/YYYY/MM/DD/<report_uuid>/`
- `data/summary_reports/YYYY/MM/DD/<summary_uuid>/`
- `data/backup/database/`

Open `/history` to search drafts and final ETE reports by date, device hierarchy, lead, verdict and status. Drafts can be resumed with **继续测试**. Any archived state can generate or re-generate a PDF snapshot directly from History; PDF generation does not change draft/final status, and draft PDFs carry the existing DRAFT watermark. Preserve `data/` during upgrades.

## Test management dashboard

Open `/dashboard` for the centralized ETE management view. The page now opens directly from the server-side local report archive, so existing historical devices and completed/in-progress results appear immediately **without querying Oracle**. In this local-history mode, untested-device count and completion rate are intentionally shown as unknown because there is no authoritative device population yet.

Enter an area, substation, or feeder and click **查询** to switch to device-coverage mode. Only then does the dashboard read the current SMART-device inventory (Oracle remains strictly SELECT-only) and merge it with local ETE history to calculate total/tested/in-progress/untested devices, Pass/Pass with comments/Fail counts, completion rate, pass rate, per-feeder statistics and device details. Date filters restrict local report history and do not by themselves trigger an Oracle inventory query.

**导出总体报表** creates an immutable summary snapshot below `data/summary_reports/` and provides PDF when Edge/Chrome/Chromium is available, with HTML/JSON retained as the durable fallback. The SMART-device inventory is cached in SQLite so scoped coverage queries can fall back to the most recent inventory when Oracle is temporarily unavailable.

## Project layout
- `src/distribution_signal_verifier/` — Python application code
- `web/` — report UI template
- `config/` — configuration templates/private local configuration
- `scripts/` — setup, run and release build scripts
- `examples/` — offline example data
- `docs/` — deployment/release documentation
- `tests/` — automated tests

## Development
```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

Offline example mode:
```powershell
.\scripts\run.ps1 -UseExampleData
```

## Build release
```powershell
.\scripts\build_release.ps1
```

The customer-facing ZIP is generated under `release/`. Do not distribute the source tree, `.venv`, build intermediates, tests, or private development files to end users.


## Oracle safety

Oracle access is **strictly read-only**. Every Oracle execution path validates SQL before execution and accepts only a single `SELECT` or `WITH ... SELECT` query. DML, DDL, transaction-control statements, `SELECT ... FOR UPDATE`, PL/SQL execution, and known side-effect package calls are rejected before they reach the Oracle cursor. Local SQLite/JSON/PDF report storage remains writable and is separate from Oracle. For defense in depth, deploy with an Oracle account that has SELECT-only privileges.