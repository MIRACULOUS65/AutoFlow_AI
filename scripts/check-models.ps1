# AutoFlow AI - inspect + verify configured models (no secrets printed).
# Usage:  .\scripts\check-models.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $root "ai-ml")
try {
    Write-Host "== Model manifest ==" -ForegroundColor Cyan
    uv run python -m autoflow_ai.cli model list

    Write-Host "`n== Verify providers (reports configured/missing env keys, never values) ==" -ForegroundColor Cyan
    foreach ($m in @("local-deterministic", "nvidia", "qwen", "embedding")) {
        Write-Host "-- $m --" -ForegroundColor Yellow
        uv run python -m autoflow_ai.cli model verify $m
    }
}
finally {
    Pop-Location
}
