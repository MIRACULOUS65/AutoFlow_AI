# AutoFlow AI — Backend Control Plane

The authoritative, durable, API-first workflow **control plane** for AutoFlow
AI. It sits between the Electron desktop client and the future AI/ML +
execution systems, and coordinates them without owning their intelligence.

> The intelligence decides *what* should happen. The control plane controls
> *whether, when, and under what authority* it happens. The execution runtime
> performs it. Verification determines whether it actually worked.

This backend runs **today, entirely on mocks** (orchestrator, agents, tools,
verifier, recovery, policy). Real implementations plug in later behind the same
interfaces — no API, database, or frontend rewrite.

---

## Architecture

```text
Electron ──REST+SSE──▶ FastAPI ──▶ Control Plane ──queue──▶ Worker
                                    (auth, tenancy,          │
                                     tasks, state machine,   ├─▶ Orchestrator (mock→real)
                                     policy, approvals,      ├─▶ Agent Runtime (mock→real)
                                     events, audit)          ├─▶ Tool Runtime (mock→real)
                                          │                  ├─▶ Verifier (mock→real)
                                          ▼                  └─▶ Recovery (mock→real)
                                      PostgreSQL
```

Layering is strict: `API → services → domain → repositories → database`, with
external intelligence reached only through interfaces (`app/orchestration`,
`app/agents`, `app/tools`, `app/verification`, `app/recovery`, `app/policy`).
The single place that flips mock → real is `app/runtime.py`.

### Non-negotiable invariants

1. No LLM has unrestricted side-effect authority.
2. Material actions require deterministic validation.
3. Material execution requires verification (tool success ≠ business success).
4. Approval binds to exact plan/action identity via an action hash.
5. Authorization is independent of retrieval relevance.
6. The desktop is a client, not an authority.
7. Execution state is durable; recovery is bounded; everything is auditable.

---

## Prerequisites

- Python 3.12+ (developed and tested on 3.14)
- No infra required for the default dev setup (SQLite + in-process queue)
- Optional for the production-style stack: Docker (PostgreSQL + Redis)

---

## Setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -e ".[dev]"
copy .env.example .env             # cp on macOS/Linux
```

The dev default in `.env` uses SQLite and an in-process queue, so the backend
runs with **zero external services**.

---

## Environment

Key variables (see `.env.example`):

| Variable            | Default                              | Purpose                                   |
| ------------------- | ------------------------------------ | ----------------------------------------- |
| `DATABASE_URL`      | `sqlite+aiosqlite:///./autoflow.db`  | Durable state store                       |
| `REDIS_URL`         | *(empty)*                            | Empty ⇒ in-process queue; else Redis      |
| `RUN_INLINE_WORKER` | `true`                               | Run the worker inside the API process     |
| `*_MODE`            | `mock`                               | Component modes (orchestrator/agent/…)    |
| `ARTIFACT_STORAGE_DIR` | `./artifacts`                     | Local artifact bytes                      |
| `CORS_ORIGINS`      | localhost:3000, app://.              | Allowed desktop origins                   |

---

## Database & migrations

- **Dev (SQLite):** tables are created automatically on startup — nothing to do.
- **Production (PostgreSQL):** set `DATABASE_URL` (e.g.
  `postgresql+asyncpg://autoflow:autoflow@localhost:5432/autoflow`), then:

  ```bash
  alembic upgrade head
  ```

`migrations/env.py` reads the sync form of `DATABASE_URL` from settings.

---

## Running

Set `PYTHONPATH` to the backend dir (or activate the venv from it).

```bash
# API (with inline worker by default)
python -m uvicorn app.main:app --reload --port 8000

# Standalone worker (production; set RUN_INLINE_WORKER=false)
python -m app.workers.task_worker

# Seed development data (idempotent)
python -m scripts.seed          # add --force to reseed
```

Then open:

- Swagger UI: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health>
- Version + modes: <http://127.0.0.1:8000/version>

### Production-style stack

```bash
docker compose up -d            # PostgreSQL + Redis
# set DATABASE_URL + REDIS_URL + RUN_INLINE_WORKER=false in .env
alembic upgrade head
python -m uvicorn app.main:app --port 8000
python -m app.workers.task_worker
```

---

## API surface

Base path `/api/v1`. Highlights:

| Area       | Endpoints                                                                 |
| ---------- | ------------------------------------------------------------------------- |
| Auth       | `POST /auth/login`, `GET /auth/me`                                        |
| Tasks      | `POST /tasks` (Idempotency-Key), `GET /tasks`, `GET /tasks/{id}`, `POST /tasks/{id}/cancel` |
| Plans      | `GET /tasks/{id}/plans`, `GET /tasks/{id}/plans/{version}`                |
| Executions | `GET /executions`, `GET /executions/{id}`, `pause`/`resume`/`cancel`, `GET /executions/{id}/steps` |
| Events     | `GET /executions/{id}/events?after=<seq>`, `GET /executions/{id}/stream` (SSE) |
| Approvals  | `GET /approvals`, `GET /approvals/{id}`, `POST .../approve`, `POST .../reject` |
| Artifacts  | `GET /artifacts`, `GET /artifacts/{id}`, `GET /artifacts/{id}/download`   |
| Registry   | `GET /agents`, `GET /workflows`, `GET /knowledge/sources`, `GET /workspaces` |

All errors use the envelope:

```json
{ "error": { "code": "INVALID_STATE_TRANSITION", "message": "...", "request_id": "req_..." } }
```

Auth is mock: send `Authorization: Bearer dev` (any non-empty token maps to the
seeded operator).

---

## Mock mode

Every intelligence/execution component is a deterministic mock:

- **MockOrchestrator** — flagship goal → 9-step plan (with an approval + send).
- **MockAgentRuntime** — proposes structured actions; never executes them.
- **MockToolRuntime** — deterministic tools, no real side effects.
- **MockVerifier** — passes unless a step is flagged `force_fail`.
- **MockRecoveryManager** — re-observe → alternate-path → recover, bounded.
- **MockPolicyEngine** — external sends are HIGH risk and require approval.

Flip any to real via `*_MODE=real` in `.env` and implement the interface in
`app/runtime.py`.

---

## Flagship flow

```text
POST /tasks "Create my weekly operations report"
  → QUEUED → PLANNING → VALIDATING → RUNNING (steps 1–6)
  → AWAITING_APPROVAL  (external email send is HIGH risk)
  → approve
  → RUNNING (send) → VERIFYING → COMPLETE
  → artifact.created, execution.completed
```

Also seeded: a task parked in `RECOVERY` and one that safely `FAILED`.

---

## Testing

```bash
python -m pytest                 # unit + api + integration
```

Covers the state machine, action-hash binding, idempotency, RBAC, the full
flagship E2E over HTTP, event replay, reject→blocked, and double-approve
conflict.

---

## Frontend integration

The desktop keeps its local mock repository as the default (zero-backend). A
backend adapter lives at `desktop/lib/api/` (`backendRepository` +
`subscribeToExecutionEvents`) implementing the same domain shape over HTTP+SSE,
selectable via `NEXT_PUBLIC_API_URL`. Pages and the store are unchanged; the
adapter maps the control plane's snake_case DTOs to the frontend's camelCase
model.

To connect the desktop to a live backend:

```bash
# backend
python -m uvicorn app.main:app --port 8000
python -m scripts.seed
# desktop/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

---

## Contract fixtures

`fixtures/*.json` are the shared request/expectation fixtures the ML team's
orchestrator and agent implementations are validated against. See
`fixtures/README.md`.

---

## Production notes

- PostgreSQL is the authoritative store; Redis is a transient queue only.
- Executions use optimistic concurrency (`version`) + durable state so workers
  can restart without replaying committed side effects.
- Provider secrets never live in the renderer or in code; audit logs never
  record secrets or hidden reasoning.
- Do not overbuild: this is a clean modular monolith with scalable interfaces,
  not a premature distributed system.
