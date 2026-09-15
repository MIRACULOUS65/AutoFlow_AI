# AutoFlow AI

A local, evidence-driven agentic system. From one natural-language instruction it
plans, delegates to specialist agents, grounds itself in retrieval + memory +
real web research, operates real applications (documents, browser, desktop)
through a tool-authority chain, verifies every step with independent evidence,
and reports success **only when the evidence proves it**. It runs on your
machine, streams every step live to a browser UI, and never fakes progress.

> **Honesty first.** Retrieval is not authorization. Model confidence is not
> verification. Tool success is not task success. A failed verification means
> NOT VERIFIED — never success. Every capability below is labeled LIVE /
> INTEGRATION / SIMULATION / SKIPPED so you always know what actually ran.

---

### Table of contents

1. [What it does](#what-it-does)
2. [The AI/ML models — every model, how it works end to end](#the-aiml-models)
3. [The agents — the specialist workforce](#the-agents)
4. [How a task flows end to end (no hallucination)](#how-a-task-flows-end-to-end)
5. [The frontend — running automation from the browser](#the-frontend)
6. [Quick start](#quick-start)
7. [The local API](#the-local-api)
8. [CLI reference](#cli-reference)
9. [Configuration](#configuration)
10. [Testing & verification](#testing--verification)
11. [Security](#security)
12. [Capability matrix](#capability-matrix)

---

## What it does

- **Agentic runtime** — a supervisor decomposes a mission, delegates to
  capability-matched specialists, and an independent critic gates completion.
- **Grounding** — RAG knowledge + workflow memory + live web research + session
  observations are merged by an EvidenceBroker with trust + provenance.
- **Real execution** — real document edit/save, semantic browser/desktop
  control, and an on-device tool-calling model that drives Windows apps.
- **Live streaming** — every plan step, tool call, observation and verification
  streams to the browser over Server-Sent Events (SSE).
- **Simulation + live** — run the whole loop deterministically first, then flip
  to real execution where configured.

---

## The AI/ML models

AutoFlow uses **four model tiers**. Every one is real and every one has a defined
job in the pipeline. All remote models speak the OpenAI-compatible Chat
Completions API, so any compatible provider works by setting a base URL + key.

| # | Model | Runtime id | Role in the pipeline | Runs where | Status |
|---|---|---|---|---|---|
| 1 | **NVIDIA `llama-3.2-11b-vision-instruct`** | `model_primary01` | Primary planner + executor + tool-caller + vision | NVIDIA NIM cloud | INTEGRATION (LIVE when key set) |
| 2 | **Qwen `Qwen3-8B` (ModelScope)** | `model_secondary01` | Secondary reasoning / fallback (streaming) | ModelScope cloud | INTEGRATION (LIVE when key set) |
| 3 | **Local deterministic rule engine** | `model_local01` | Offline reproducible baseline + simulation | On CPU, no key | LIVE (always) |
| 4 | **Cactus Needle 2 (45M, fine-tuned)** | `needle_agent` | On-device natural-language → tool calls for Windows automation | On CPU, ~110MB RAM, no key | LIVE (weights bundled) |

### 1 & 2 — the cloud planners/executors (NVIDIA + Qwen)

These are the "brains" for planning and structured reasoning. They are used
through a **model gateway** that:
- validates every model output against a **typed schema** (a plan, a tool call,
  a decision) — malformed or hallucinated output is rejected, not executed;
- **fails closed** on timeouts (reports failure rather than guessing);
- **routes** by role + priority (primary → secondary fallback) and redacts
  secrets from every prompt, log and trace.

The model only *proposes*. Deterministic tools perform side effects and
independent verifiers confirm them, so a model hallucination can never become a
completed task.

### 3 — the local deterministic model (always on)

A rule engine (`local-rule` provider) that is always available with zero config.
It powers **simulation mode** (the full agent loop over a deterministic
environment) and acts as a reproducible baseline in the Model Lab. It is not a
semantic LLM — it is deterministic, offline, and never hallucinates because it
does not generate free text.

### 4 — Cactus Needle 2 (on-device tool caller)

A 45M-parameter model ([Cactus Compute](https://cactuscompute.com/)) fine-tuned
to turn plain instructions into tool calls for 26+ real Windows tasks (Word,
notes, browser, YouTube, Gmail draft, file ops, and more). The **fine-tuned
weights (`my_agent.cact`, ~14MB) ship inside the repo**, so any clone or
`pip install` gets a working on-device agent — no download, no API key, runs on
the CPU. It has a built-in anti-hallucination guard: it refuses instructions it
cannot ground ("ungrounded content") rather than inventing actions.

```powershell
uv pip install cactus-needle
uv run python -m autoflow_ai.cli needle run "make a note that says buy milk" --execute
```

### How the models are graded (Model Lab)

The **Model Lab** benchmarks and compares all configured models *structurally*,
not by vibes: schema validity, malformed-output handling, and hallucination
resistance, with secret-free observability.

```powershell
uv run python -m autoflow_ai.cli model lab benchmark
uv run python -m autoflow_ai.cli model lab compare --models nvidia,qwen,deterministic
```

---

## The agents

Missions are executed by a **society of specialist agents** coordinated by a
supervisor, with an independent critic. Each agent maps its task to a concrete,
schema-checked tool call — it never fakes work, and refuses tasks outside its
capability (returns UNSUPPORTED, not a fake success).

| Agent | Capability | What it really does |
|---|---|---|
| **Supervisor** | orchestration | Decomposes the mission, delegates tasks, gates completion on the critic |
| **Document** | document_editing | Real inspect → edit → save of `.txt`/`.md`/`.docx`; applies the instructed content change |
| **Research** | knowledge_retrieval | Synthesizes findings from authorized evidence (RAG/memory/web) |
| **Spreadsheet** | data_analysis | Structured cell/range/formula actions |
| **QA / Critic** | verification | Independently re-checks each claim against evidence; the completion gate |
| **Communication** | email | Composes email/Gmail drafts; send is approval-bound |
| **Browser** | web_navigation | One semantic `browser.*` action per step (observe → act → verify DOM) |
| **Computer** | desktop_automation | Semantic Windows UIA control (not coordinate replay) |
| **Presentation / Coding** | generic tool | Propose a registered tool or NOOP honestly |
| **Needle (on-device)** | tool_calling | 45M model that selects + executes Windows tool calls directly |

Every agent action flows through the **tool authority chain**: propose → policy
check → deterministic execute → observe real state → verify. Approval binds to
the exact action; any change invalidates it.

---

## How a task flows end to end

```
USER (browser UI or CLI)
   │  natural-language instruction (+ optional target file)
   ▼
LOCAL API  (autoflow serve, stdlib http.server)
   ▼
PLANNER            model (NVIDIA/Qwen) OR deterministic → typed TaskGraph (schema-validated)
   ▼
SUPERVISOR         delegates each task to a capability-matched specialist
   ▼
SPECIALIST         proposes ONE tool call (schema-checked)
   ▼
TOOL AUTHORITY     policy + permission check → deterministic execution (real side effect)
   ▼
OBSERVATION        read the real resulting state (file hash, DOM, window, disk)
   ▼
INDEPENDENT CRITIC verifies the claim against the observation — PASS or NOT VERIFIED
   ▼
ARTIFACTS + AUDIT + live SSE event stream  →  browser UI
```

**Why it does not hallucinate a success:**
1. The model only *proposes*; it never performs a side effect directly.
2. Every proposal is validated against a typed schema before it can run.
3. Side effects are done by deterministic tools, then the resulting **real
   state is observed** (e.g. the file is reopened from disk).
4. An **independent critic** confirms the requested change is actually present
   (e.g. the edited text is really in the file). If not → the mission is
   `failed`, never `complete`. This is enforced and tested.

---

## The frontend

The frontend is a single static page **served by the API at `/`** — no build
toolchain, no framework. It talks only HTTP/SSE to the local API (never touches
agent classes directly), so the same contract backs the UI, the CLI and any
external client.

### What you can do from the browser

1. **Open** <http://127.0.0.1:8770> after `autoflow serve`.
2. **Type a mission** in plain language.
3. **Pick a mode:**
   - **Simulation** — runs the full agent loop deterministically (safe preview,
     no real side effects).
   - **Real (edit a file on disk)** — enter an absolute path to a `.txt`/`.md`/
     `.docx` file; the agent actually edits and saves it.
4. **Pick a model** from the dropdown (populated live from `/models`).
5. **Click Run Mission** and watch the live timeline: plan → delegation →
   tool calls → observations → verification → artifacts, streamed over SSE.
6. **See the result honestly:** the UI shows **COMPLETED only when the backend
   reports a verified completion**. A mission that failed verification shows
   FAILED with the reason — it can never display a fake success.

### End-to-end example (real file edit from the UI)

- Mission: `replace the word DRAFT with FINAL and save the document`
- Mode: **Real**, target: `C:\path\to\report.txt`
- Result: the file on disk changes DRAFT → FINAL, the timeline shows the real
  edit + verify events, and the verification panel confirms the change landed.
  If the word wasn't present, the mission reports `failed` (no false success).

### Uploading / choosing the file to automate

For real-file missions the frontend takes an absolute file path (the API and
agents run on the same machine, so the agent reads/writes that path directly).
For the on-device Windows agent, use the CLI `needle run ... --execute` or the
API to drive app-level actions (Word, notes, browser, YouTube, Gmail draft).

---

## Quick start

**Windows / PowerShell:**

```powershell
cd ai-ml
uv sync                                  # install deps
uv pip install cactus-needle             # optional: on-device Needle agent
copy ..\.env.example ..\.env             # then edit ..\.env for live cloud models
uv run python -m autoflow_ai.cli doctor  # environment diagnostics
uv run python -m autoflow_ai.cli demo    # deterministic flagship demo
uv run python -m autoflow_ai.cli serve   # http://127.0.0.1:8770
```

One-command scripts also exist: `.\scripts\bootstrap.ps1`, `run.ps1`,
`test.ps1`, `simulate.ps1`, `run-flagship.ps1`, `check-models.ps1`.

---

## The local API

Start with `autoflow serve`. Full contract in [`docs/API.md`](docs/API.md).

| Method + route | Purpose |
|---|---|
| `GET /` | frontend single page |
| `GET /health` | real subsystem + provider health |
| `GET /capabilities` | real capability probe |
| `GET /models` | configured models |
| `POST /models/{id}/test` | one benchmark task against a model |
| `GET /missions` · `POST /missions` | list / create a mission |
| `POST /missions/{id}/simulate` | run the deterministic full loop |
| `POST /missions/{id}/run` | **real** mission against a `target_path` |
| `GET /missions/{id}` | mission state (`result` is null until verified) |
| `GET /missions/{id}/events` | SSE stream of canonical events |
| `GET /missions/{id}/trace` · `/artifacts` | full trace / artifacts |

Every event is secret-redacted and shares one shape (`mission_id`, `event_id`,
`timestamp`, `source`, `type`, `status`, `payload`).

---

## CLI reference

```powershell
# diagnostics + demo
autoflow doctor
autoflow demo

# models
autoflow model list | info | install <id> | verify <id>
autoflow model test
autoflow model lab list | test <id> | benchmark | compare --models nvidia,qwen,deterministic
autoflow model console

# missions
autoflow mission simulate --live
autoflow mission run "replace the word DRAFT with FINAL and save the document" --file report.txt

# on-device Windows automation (Cactus Needle 2)
autoflow needle run "write hi my name is sam into notes.docx"           # plan only (safe)
autoflow needle run "make a note that says buy milk" --execute          # real action

# knowledge / research / server
autoflow rag search "your query"
autoflow research run "latest python version" --allow-web --deep-read
autoflow serve --host 127.0.0.1 --port 8770
```

(Prefix with `uv run python -m autoflow_ai.cli` or install the package to get the
`autoflow` entry point.)

---

## Configuration

Copy `.env.example` to `.env`. Everything runs offline with the local
deterministic model and the on-device Needle agent if you configure nothing. To
enable the cloud planners set `PRIMARY_MODEL_*` (NVIDIA) and/or
`SECONDARY_MODEL_*` (Qwen). See [`docs/MODELS.md`](docs/MODELS.md).

Key variables: `PRIMARY_MODEL_BASE_URL/ID/API_KEY`, `SECONDARY_MODEL_*`,
`AUTOFLOW_HOST/PORT`, `AUTOFLOW_MODEL_HOME`, `AUTOFLOW_NEEDLE_WEIGHTS/OUTPUT`,
and the opt-in gates `AUTOFLOW_ALLOW_WEB` / `AUTOFLOW_REAL_WORD` /
`AUTOFLOW_REAL_GMAIL` / `AUTOFLOW_LIVE_NVIDIA` / `AUTOFLOW_NEEDLE_LIVE`.

---

## Testing & verification

```powershell
cd ai-ml
uv run python -m compileall -q src
uv run pytest -q                                            # full suite: 1068 passed
uv run pytest -q -k "not real_notepad and not real_word"   # skip slow real-desktop
```

Environment-gated live tests stay honestly **SKIPPED** unless the matching flag
is set. Reference: `1068 passed, 8 skipped` on Python 3.14 / Windows.

---

## Security

- `.env` is gitignored and never committed; secrets are redacted from logs,
  traces, datasets and events.
- Cloud model weights and caches are gitignored. **Exception:** the small
  on-device Needle weights (`my_agent.cact`, ~14MB) are intentionally committed
  so the on-device agent works from a clean clone.
- The API binds to localhost only — do not expose it to untrusted networks.

---

## Capability matrix

Exact LIVE / INTEGRATION / SIMULATION / SKIPPED status per capability:
[`docs/CAPABILITY_MATRIX.md`](docs/CAPABILITY_MATRIX.md). Deployment details:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Final report:
[`docs/FINAL_DEPLOYMENT_REPORT.md`](docs/FINAL_DEPLOYMENT_REPORT.md).
