# Convenience dev scripts (Windows PowerShell).
#   . .\scripts\dev.ps1     # dot-source to load functions
# then: Backend-Dev | Backend-Worker | Backend-Seed | Backend-Test | Backend-Migrate

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "."
$PY = ".\.venv\Scripts\python.exe"

function Backend-Dev    { & $PY -m uvicorn app.main:app --reload --port 8000 }
function Backend-Worker { $env:RUN_INLINE_WORKER = "false"; & $PY -m app.workers.task_worker }
function Backend-Seed   { & $PY -m scripts.seed @args }
function Backend-Test   { & $PY -m pytest -p no:cacheprovider @args }
function Backend-Typecheck { & $PY -m mypy app @args }
function Backend-Lint   { & $PY -m ruff check app @args }
function Backend-Migrate { & $PY -m alembic upgrade head }

Write-Host "Loaded: Backend-Dev, Backend-Worker, Backend-Seed, Backend-Test, Backend-Typecheck, Backend-Lint, Backend-Migrate"
