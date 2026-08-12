$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment is missing. Run scripts\setup.ps1 first."
}
$env:PYTHONPATH = $projectRoot
Set-Location $projectRoot
& $python -m backend.run

