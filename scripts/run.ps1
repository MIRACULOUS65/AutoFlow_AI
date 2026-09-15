# AutoFlow AI - start the local orchestration API + frontend.
# Usage:  .\scripts\run.ps1 [-BindHost 127.0.0.1] [-Port 8770]
param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8770
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $root "ai-ml")
try {
    Write-Host "Starting AutoFlow API at http://${BindHost}:${Port}" -ForegroundColor Cyan
    Write-Host "Open that URL in a browser, then click Run Mission (Simulation)." -ForegroundColor Yellow
    uv run python -m autoflow_ai.cli serve --host $BindHost --port $Port
}
finally {
    Pop-Location
}
