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
    $pnpm = Get-Command "pnpm.cmd" -ErrorAction SilentlyContinue
    $npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if ($npm) {
        Write-Host "Installing frontend with npm..." -ForegroundColor Cyan
        if (Test-Path -LiteralPath "package-lock.json") { & $npm.Source ci }
        else { & $npm.Source install }
        & $npm.Source run build
    } elseif ($pnpm) {
        Write-Host "npm is unavailable; installing frontend with pnpm..." -ForegroundColor Yellow
        & $pnpm.Source install --frozen-lockfile=$false
        & $pnpm.Source run build
    } else {
        throw "Node.js package manager not found. Install Node.js 20 or newer, reopen PowerShell, and rerun setup."
    }
} finally {
    Pop-Location
}

$model = Join-Path $projectRoot "models\yolo26\yolo26s.pt"
if (-not (Test-Path -LiteralPath $model)) {
    Write-Warning "YOLO weights are missing: $model"
}
Write-Host "Setup complete. Edit .env, flash firmware, then run scripts\start.ps1." -ForegroundColor Green
