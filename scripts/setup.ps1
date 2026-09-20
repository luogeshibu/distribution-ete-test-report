$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$venvRoot = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) { python -m venv $venvRoot }
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")
& $venvPython -m pip install pyinstaller
Write-Host "Environment setup complete."
Write-Host "Run:   .\scripts\run.ps1"
Write-Host "Build: .\scripts\build_release.ps1"