# AutoFlow AI - compile + run the test suite.
# Usage:  .\scripts\test.ps1 [-Full]
#   default skips the slow real-desktop tests; -Full runs everything.
param([switch]$Full)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# Close leftover automation targets so real-desktop tests are not flaky.
Get-Process notepad, winword -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

Push-Location (Join-Path $root "ai-ml")
try {
    Write-Host "Byte-compiling sources..." -ForegroundColor Yellow
    uv run python -m compileall -q src

    if ($Full) {
        Write-Host "Running FULL test suite..." -ForegroundColor Yellow
        uv run pytest -q
    } else {
        Write-Host "Running test suite (skipping slow real-desktop)..." -ForegroundColor Yellow
        uv run pytest -q -k "not real_notepad and not real_word"
    }
}
finally {
    Pop-Location
}
