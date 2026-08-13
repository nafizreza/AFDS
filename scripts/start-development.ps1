$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Run scripts\setup.ps1 first." }

$backend = Start-Process -FilePath $python -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
Write-Host "Backend PID: $($backend.Id)" -ForegroundColor DarkGray
Push-Location (Join-Path $projectRoot "frontend")
try {
    $pnpm = Get-Command "pnpm.cmd" -ErrorAction SilentlyContinue
    $npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if ($npm) { & $npm.Source run dev }
    elseif ($pnpm) { & $pnpm.Source run dev }
    else { throw "Node.js package manager not found." }
} finally {
    Pop-Location
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
}
