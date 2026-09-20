# Release

Current version: **V1.0.2**

## V1.0.2
- Fix release configuration generation when `print_password` is empty.
- Keep PyInstaller `getpass` hidden import and full `oracledb` collection.
- Remove generated/development-only files from the publish-source package.
- Use `VERSION` as the single version source.
- Keep SQL/query/UI behavior unchanged from the V1.0.0 baseline.

## Build

```powershell
.\setup.ps1
.\build_release.ps1
```

The distributable ZIP is generated under `release` and is not part of the source package.