# Distribution Signal Verifier

ADMS 配网 RMU/RTU 信号端到端核验与投运报告工具。

## Version
V1.1.2

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