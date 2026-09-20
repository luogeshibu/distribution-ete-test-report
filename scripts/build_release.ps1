param([string]$OutputDirectory = "release")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
$setupScript = Join-Path $projectRoot "scripts\setup.ps1"

if (-not (Test-Path -LiteralPath $python)) { & $setupScript }
if (-not (Test-Path -LiteralPath $pyinstaller)) { & $python -m pip install pyinstaller }

$version = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($version)) { throw "VERSION is empty." }

$releaseRoot = Join-Path $projectRoot $OutputDirectory
$work = Join-Path $releaseRoot "_build"
$packageName = "Distribution-Signal-Verifier-v$version"
$package = Join-Path $releaseRoot $packageName
$zip = Join-Path $releaseRoot ("{0}-release.zip" -f $packageName)

Remove-Item $work, $package, $zip -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $work, $package | Out-Null

# Validate source before packaging.
$env:PYTHONPATH = Join-Path $projectRoot "src"
$sourceFiles = @(
    (Join-Path $projectRoot "src\distribution_signal_verifier\distribution_signal_verifier.py"),
    (Join-Path $projectRoot "src\distribution_signal_verifier\live_report_server.py"),
    (Join-Path $projectRoot "src\distribution_signal_verifier\distribution_report_launcher.py")
)
& $python -m py_compile @sourceFiles
if ($LASTEXITCODE -ne 0) { throw "Python source validation failed." }

# Verify runtime dependencies before starting the expensive EXE build.
& $python -c "import oracledb, cryptography, cffi; print('Oracle runtime dependencies OK')"
if ($LASTEXITCODE -ne 0) { throw "Oracle runtime dependencies are incomplete. Run .\scripts\setup.ps1 first." }

# Build a standalone Windows executable. python-oracledb thin mode loads
# cryptography dynamically for authentication, so collect both packages and
# their runtime dependencies explicitly.
& $pyinstaller --noconfirm --clean --onefile --name "DistributionSignalVerifier" `
    --paths (Join-Path $projectRoot "src") `
    --add-data ((Join-Path $projectRoot "web\distribution_report.html") + ";.") `
    --hidden-import getpass `
    --collect-all oracledb `
    --collect-all cryptography `
    --collect-all cffi `
    --hidden-import cryptography `
    --hidden-import cryptography.hazmat.bindings._rust `
    --distpath (Join-Path $work "bin") `
    --workpath (Join-Path $work "work") `
    --specpath (Join-Path $work "spec") `
    (Join-Path $projectRoot "src\distribution_signal_verifier\distribution_report_launcher.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

$exeSource = Join-Path $work "bin\DistributionSignalVerifier.exe"
if (-not (Test-Path -LiteralPath $exeSource)) { throw "Build completed but executable was not produced: $exeSource" }
Copy-Item -LiteralPath $exeSource -Destination $package

# Use the same canonical configuration as source execution.
# This keeps run.ps1 and packaged EXE behavior aligned.
$sourceConfigPath = Join-Path $projectRoot "config\report_config.json"
if (-not (Test-Path -LiteralPath $sourceConfigPath)) {
    throw "Missing canonical configuration: $sourceConfigPath"
}
$configPath = Join-Path $package "report_config.json"
Copy-Item -LiteralPath $sourceConfigPath -Destination $configPath -Force

# Fail the release if config is empty, invalid, or structurally incomplete.
if (-not (Test-Path -LiteralPath $configPath) -or (Get-Item $configPath).Length -eq 0) {
    throw "Release configuration was not generated."
}
try {
    $validated = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if ($null -eq $validated.server -or $null -eq $validated.oracle -or $null -eq $validated.security) {
        throw "Required configuration sections are missing."
    }
} catch {
    throw "Generated release configuration is invalid: $($_.Exception.Message)"
}

# Minimal operator-facing release contents only.
Set-Content -LiteralPath (Join-Path $package "VERSION") -Value $version -Encoding ASCII
Copy-Item -LiteralPath (Join-Path $projectRoot "docs\DEPLOYMENT.md") -Destination (Join-Path $package "README.txt")
New-Item -ItemType Directory -Force -Path (Join-Path $package "logs") | Out-Null

Compress-Archive -Path $package -DestinationPath $zip -Force
if (-not (Test-Path -LiteralPath $zip)) { throw "Release ZIP was not created." }

Remove-Item $work -Recurse -Force
Write-Host ""
Write-Host "BUILD SUCCESS" -ForegroundColor Green
Write-Host "Version : $version"
Write-Host "Package : $package"
Write-Host "ZIP     : $zip"