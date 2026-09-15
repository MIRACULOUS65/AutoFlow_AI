# Convenience targets (macOS/Linux). Windows: use scripts/dev.ps1.
export PYTHONPATH := .
PY := .venv/bin/python

.PHONY: dev worker seed test typecheck lint migrate

dev:
	$(PY) -m uvicorn app.main:app --reload --port 8000

worker:
	RUN_INLINE_WORKER=false $(PY) -m app.workers.task_worker

seed:
	$(PY) -m scripts.seed

test:
	$(PY) -m pytest -p no:cacheprovider

typecheck:
	$(PY) -m mypy app

lint:
	$(PY) -m ruff check app

migrate:
	$(PY) -m alembic upgrade head
