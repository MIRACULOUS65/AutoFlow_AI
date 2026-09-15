# AutoFlow AI - run a deterministic full-loop mission simulation with live trace.
# Usage:  .\scripts\simulate.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $root "ai-ml")
try {
    Write-Host "Running deterministic mission simulation (live trace)..." -ForegroundColor Cyan
    uv run python -m autoflow_ai.cli mission simulate --live
}
finally {
    Pop-Location
}
