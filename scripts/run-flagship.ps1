# AutoFlow AI - run the flagship demo (deterministic end-to-end, complete:true).
# Usage:  .\scripts\run-flagship.ps1 [-Live]
#   -Live attempts real capabilities where configured (models/web/desktop).
param([switch]$Live)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $root "ai-ml")
try {
    if ($Live) {
        Write-Host "Running flagship demo (LIVE where configured)..." -ForegroundColor Cyan
        uv run python -m autoflow_ai.cli demo --live
    } else {
        Write-Host "Running flagship demo (deterministic simulation)..." -ForegroundColor Cyan
        uv run python -m autoflow_ai.cli demo
    }
}
finally {
    Pop-Location
}
