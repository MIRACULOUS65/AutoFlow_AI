# AutoFlow AI - bootstrap a clean local environment.
# Usage:  .\scripts\bootstrap.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== AutoFlow AI bootstrap ==" -ForegroundColor Cyan

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed. See https://docs.astral.sh/uv/getting-started/installation/"
}

Push-Location (Join-Path $root "ai-ml")
try {
    Write-Host "Installing dependencies (uv sync)..." -ForegroundColor Yellow
    uv sync

    $envFile = Join-Path $root ".env"
    $envExample = Join-Path $root ".env.example"
    if (-not (Test-Path $envFile)) {
        Copy-Item $envExample $envFile
        Write-Host "Created .env from .env.example (edit it to enable live models)." -ForegroundColor Green
    } else {
        Write-Host ".env already exists - left untouched." -ForegroundColor Green
    }

    Write-Host "Running environment diagnostics..." -ForegroundColor Yellow
    uv run python -m autoflow_ai.cli doctor
    Write-Host "Bootstrap complete. Next: .\scripts\run.ps1" -ForegroundColor Cyan
}
finally {
    Pop-Location
}
