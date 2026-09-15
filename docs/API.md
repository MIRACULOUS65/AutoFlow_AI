# AutoFlow AI — Local Orchestration API

The local API is a **Python stdlib `http.server`** service (zero extra
dependencies) started with `autoflow serve`. It binds to localhost only and
serves both the JSON API and the single-page frontend at `/`. The frontend never
touches agent classes directly — it only speaks HTTP to this API, so the same
contract backs the CLI, the browser UI, and any external client.

Start it:

```powershell
cd ai-ml
uv run python -m autoflow_ai.cli serve --host 127.0.0.1 --port 8770
```

Defaults come from `AUTOFLOW_HOST` (127.0.0.1) and `AUTOFLOW_PORT` (8770).

## Conventions

- All request/response bodies are JSON (`Content-Type: application/json`).
- Request bodies are capped at **256 KB**; oversized bodies get `400` and the
  connection is closed.
- Every mission id has the form `exec_<token>` (e.g. `exec_exec120355123456`).
- Secrets are **redacted** from every response, event and trace.

## Endpoints

### `GET /`
Serves the frontend single page (HTML). Use a browser.

### `GET /health`
Real subsystem health (reuses the model-lab provider probes — validated, not
"config exists"). Includes a `model_providers` block.

```json
{ "status": "ok", "model_providers": { "local-rule": "available", "nvidia": "unconfigured" }, "...": "..." }
```

### `GET /capabilities`
Real provider/tool capabilities.

```json
{ "providers": [ ... ], "browser": false, "desktop": false, "web": false }
```

### `GET /models`
Configured models (from the manifest + gateway). Each entry marks whether it is
`local`.

```json
{ "models": [ { "model_id": "model_local01", "provider": "local-rule", "local": true }, ... ] }
```

### `POST /models/{id}/test`
Runs one structural benchmark task against a model and reports schema validity.

```json
{ "model_id": "model_local01", "schema_valid": true, "latency_ms": 3 }
```

### `GET /missions`
Lists known missions with their current status.

### `POST /missions`
Creates a mission. Body: `{ "prompt": "...", "mode": "simulation", "model": "<id>" }`.
`prompt` is required (empty → `400`). Returns `201`:

```json
{ "mission_id": "exec_exec120355123456", "status": "created" }
```

### `POST /missions/{id}/simulate`
Runs the deterministic full-loop simulation **asynchronously** (reuses
`society.simulate_mission` over a deterministic environment — the real runtime,
not a re-implementation). Returns immediately with `status: running`. Progress
streams over the events endpoint; final state settles on `GET /missions/{id}`.

### `GET /missions/{id}`
Mission state. `status` is one of `created | running | awaiting_approval |
complete | failed`. `result` is `null` until the run actually finishes — a
mission that never ran can never report `complete` (anti-fabrication contract).

```json
{ "mission_id": "exec_...", "status": "complete",
  "result": { "complete": true, "document_verified": true } }
```

### `GET /missions/{id}/events` (SSE)
Server-Sent Events stream of canonical mission events. Supports `?after=<event_id>`
to resume. Each frame:

```
event: agent_step
data: {"mission_id":"exec_...","event_id":12,"timestamp":"...","source":"supervisor","type":"agent_step","status":"running","payload":{...}}
```

The stream runs from `mission_started` through `mission_completed` (or
`mission_failed`) then closes.

### `GET /missions/{id}/trace`
The full event list as JSON (same canonical event shape as SSE).

### `GET /missions/{id}/artifacts`
Artifacts produced by the mission (reports, verified documents, etc.).

## Canonical event contract

Every event — over SSE, in the trace, and in the CLI — shares one shape:

| Field | Meaning |
|---|---|
| `mission_id` | owning mission (`exec_<token>`) |
| `event_id` | monotonically increasing integer within the mission |
| `timestamp` | ISO-8601 UTC |
| `source` | emitting component (`supervisor`, `researcher`, `qa`, ...) |
| `type` | event type (see below) |
| `status` | `running` \| `complete` \| `failed` \| `awaiting_approval` |
| `payload` | secret-free structured detail |

Event types include: `mission_started`, `plan_created`, `agent_step`,
`tool_call`, `observation`, `verification`, `approval_requested`,
`artifact_created`, `mission_completed`, `mission_failed`.

## Error responses

```json
{ "error": "prompt is required" }
```

Status codes: `400` invalid/oversized body, `404` unknown route/mission, `200`
GET success, `201` mission created.

## Security notes

- Localhost bind only; no auth layer is intended for LAN/public exposure. Do not
  expose this port to untrusted networks.
- Bodies are size-limited; unknown routes return `404`.
- No secret ever appears in a response, event or trace.
