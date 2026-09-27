# Persistent runtime data

This directory belongs to the running `distribution-ete-test-report` installation and must be preserved during upgrades.

- `database/ete_reports.db` — SQLite report index/metadata (created automatically).
- `reports/YYYY/MM/DD/<report_uuid>/` — draft/final HTML/JSON/PDF report snapshots.
- `summary_reports/YYYY/MM/DD/<summary_uuid>/` — exported station/feeder overall report snapshots.
- `backup/database/` — automatic database backups before schema migrations.

The application creates missing directories automatically. Do not ship or overwrite a production `ete_reports.db` when updating program files.
