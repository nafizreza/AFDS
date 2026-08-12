$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

Write-Host "AFDS setup: $projectRoot" -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $venvPython)) {
    py -3.10 -m venv (Join-Path $projectRoot ".venv")
}
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $projectRoot "requirements.txt")

Push-Location (Join-Path $projectRoot "frontend")
try {
    pnpm install --frozen-lockfile=$false
    pnpm run build
} finally {
    Pop-Location
}

$model = Join-Path $projectRoot "models\yolo26\yolo26s.pt"
if (-not (Test-Path -LiteralPath $model)) {
    Write-Warning "YOLO weights are missing: $model"
}
Write-Host "Setup complete. Edit .env, flash firmware, then run scripts\start.ps1." -ForegroundColor Green

