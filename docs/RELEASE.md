# Release

Current version: **V1.2.29**

## V1.2.29
- Project/delivery identity is `distribution-ete-test-report`.
- Formal Print/PDF archives the frozen report to the central service before local printing.
- Persistent data lives under the program directory in `data/` and must survive upgrades.
- Historical reports are available from `/history` with view/download functions.
- SQLite metadata uses WAL mode and schema migrations; future migrations back up the database first.
- Existing RMU/point SQL and Oracle query behavior remain unchanged.

## Build

```powershell
.\scripts\setup.ps1
.\scripts\build_release.ps1
```

The distributable ZIP is generated under `release/`. Never replace a production `data/` directory with a new empty one during an upgrade.
