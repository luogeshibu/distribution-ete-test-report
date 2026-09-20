param([string]$ListenAddress="127.0.0.1",[int]$Port=8899,[switch]$UseExampleData)
$ErrorActionPreference="Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { & (Join-Path $projectRoot "scripts\setup.ps1") }
$configPath = Join-Path $projectRoot "config\report_config.json"
if (-not (Test-Path -LiteralPath $configPath)) { throw "Missing config: $configPath" }
$env:PYTHONPATH = (Join-Path $projectRoot "src")
$argsList=@("-m","distribution_signal_verifier.live_report_server","--template",(Join-Path $projectRoot "web\distribution_report.html"),"--host",$ListenAddress,"--port",$Port)
if ($UseExampleData) {
  $argsList += @("--mapping-json",(Join-Path $projectRoot "examples\mapping.example.json"),"--distribution-signals-json",(Join-Path $projectRoot "examples\signals.example.json"))
}
& $python @argsList