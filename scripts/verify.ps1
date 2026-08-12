$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Run scripts\setup.ps1 first." }

Push-Location $projectRoot
try {
    & $python -m compileall -q backend
    & $python -m pytest
    Push-Location frontend
    try { pnpm run build } finally { Pop-Location }
    $model = "models\yolo26\yolo26s.pt"
    if (-not (Test-Path -LiteralPath $model)) { throw "YOLO model is missing." }
    Get-FileHash -Algorithm SHA256 -LiteralPath $model
} finally {
    Pop-Location
}

