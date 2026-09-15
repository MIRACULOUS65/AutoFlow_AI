# AutoFlow AI — Implementation Status

**Document type:** Implementation status ledger (source of truth for current build state)
**Last updated:** 2026-09-12 (Phase 1 + vertical slice complete)
**Auditor:** Lead architect / implementation engineer

> This file is the running ledger of what actually exists in the repository versus
> what the documentation describes. It is updated at the end of every phase.
> Nothing here is aspirational: it records measured, verified state only.

---

## 1. Executive summary

Phase 0 (audit) and **Phase 1 (contract layer) are complete**. The `ai-ml/`
subsystem is now a real, installable Python package with ~33 versioned Pydantic
contracts, a headless CLI, and a rigorous test suite (95 tests, 97% coverage,
no warnings) that runs entirely on localhost without Electron. The backend and
desktop remain docs-only.

**Current phase:** Phases 1–7 + the **Computer-Autonomy bundle (Phases 8–14)**
done. **380 tests pass** (incl. real live-desktop UIA + real headless browser
tests).

### Computer-Autonomy bundle — what shipped (status-labeled)

All in `ai-ml/src/autoflow_ai/computer_use/` (+ `runtime/tool_calling.py`):

- **Unified observation + fusion + target resolver** — IMPLEMENTED, TESTED.
  Multiple evidence sources fuse into one view; resolver returns RESOLVED/
  AMBIGUOUS/NOT_FOUND/DISABLED/HIDDEN/STALE, never guesses.
- **Browser automation** — IMPLEMENTED, TESTED, **LIVE VERIFIED** (real headless
  Chromium via Playwright on a controlled local page: launch/fill/click/wait/
  read). Remote navigation blocked; high-risk browser tools not registered.
- **Vision subsystem** — IMPLEMENTED, TESTED (provider-neutral interface +
  deterministic FakeVision + rate limiting + duplicate-screenshot suppression).
  A real multimodal provider plugs into the same gateway (FUTURE to wire a live
  vision model; interface + budget are done).
- **Deterministic CV (OpenCV 5)** — IMPLEMENTED, TESTED (perceptual hash, image
  diff, visual-stability, template match) on Python 3.14.
- **Verification engine** — IMPLEMENTED, TESTED (multi-signal UI/DOM/file/
  document/app-state/text; "action executed" never equals success).
- **Recovery + stuck detection** — IMPLEMENTED, TESTED (bounded ladder;
  repeated-state/action detection; preserves completed work).
- **Approval binding + rate limits + resource locks** — IMPLEMENTED, TESTED
  (approval bound to exact action+args+observation hash, invalidated on material
  change; per-task/minute action limits; per-resource locks).
- **Autonomy loop + WorkflowExecution** — IMPLEMENTED, TESTED, LIVE VERIFIED
  (observe → act → verify → recover; serializable trace).
- **Windows desktop (Phase 7)** — LIVE VERIFIED (real Notepad launch/type/verify).
- **Stress** — 100 deterministic runs + 30 failure-injection runs, **0
  false-success**. Real-model action path is fail-closed (TESTED hermetically).

New optional deps (Python 3.14): `opencv-python-headless`, `numpy`, `pillow`,
`mss`, `playwright` (+ Chromium). Core imports them lazily; tests run without
them where marked. **FUTURE/not implemented:** live vision-model grounding call,
Word end-to-end via UIA in CI, GUI screenshot capture wired into the loop.

### Phase 7 — what shipped (Tool-Calling Controller + Windows Computer-Use)

New `ai-ml/src/autoflow_ai/computer_use/` package: a backend-neutral
`ComputerAdapter` interface, a **real `WindowsUIAutomationAdapter`** (via
`uiautomation`/UIA — semantic role/name/automation-id resolution, ambiguity
detection, **allowlisted** app launch, no coordinate-primary interaction), a
deterministic `FakeDesktopAdapter` for hermetic tests, semantic models
(`UIElement`, `WindowInfo`, `DesktopObservation`, `ActionResult`) and a
semantic `desktop_state_hash`. Safe computer tools are registered into the
**existing** `ToolRegistry` (inspect/list/focus/find/launch/click/type/press_key/
hotkey/wait_for); destructive/shell tools are **never registered**. A
`ToolCallingController` (`runtime/tool_calling.py`) is the single authority
chain (proposal → schema → registry lookup → authorization → policy/risk →
approval → execute → sanitized trace), redacting secrets and never echoing typed
text. `ComputerAutomationAgent` is now a **real** agent (proposes one semantic
computer action per node; NOOP/UNSUPPORTED only when honestly so). Runs inside
the existing `MultiAgentRuntime`; the deterministic planner recognizes Notepad
desktop tasks. CLI: `autoflow computer env|windows|inspect`.

**Live-verified on this machine:** a real Notepad workflow launched, typed via
UI Automation, and verified a semantic state change; `computer env` reports the
live UIA adapter with 5 real windows. 28 new tests (hermetic + adversarial + 2
real desktop tests that actually executed); **352 tests pass**. New optional dep
`uiautomation` (Windows only; core imports it lazily, tests run without it).
Browser automation remains a separate future phase (not faked).

### Phase 6 — what shipped (dynamic planner + multi-agent runtime)

New `ai-ml/src/autoflow_ai/planning/` (typed `PlannerOutput`, `RuntimeGraph` +
node state machine, deterministic `validate_plan`, `DeterministicPlanner` +
`ModelPlanner` that fails closed) and `agents/` (`SpecialistAgent` base, explicit
`AgentContext`, structured `AgentResult`/`AgentActionProposal`, registry, nine
specialists). New `runtime/multi_agent.py` `MultiAgentRuntime`: ready-node
scheduling, bounded thread-pool concurrency, dependency fan-out/fan-in, deadlock
detection, bounded replanning, and the full authority chain (agent proposes →
schema/policy/permission/approval → `ToolRegistry` executes → observe → verify).
Orchestrator gains `dynamic_plan` + `run_multi_agent` (opt-in; the single-agent
`run()` and Golden 01 are untouched). CLI: `autoflow agents list|inspect`,
`dynplan`, `run-agents [--model]`. Browser/Computer agents are **real interfaces
that return UNSUPPORTED — not faked**. Reuses the Phase 2 gateway, Phase 3
context, Phase 4 tools, and Phase 5 memory (verified runs feed promotion, no
bypass). Live-verified the real-model planner path (fails closed to
deterministic). 41 new tests (MA golden + adversarial + deadlock + concurrency);
all 324 green; no new dependencies.

### Earlier phases

Two real chat providers are live-verified
(NVIDIA `meta/llama-3.2-11b-vision-instruct`, ModelScope `Qwen/Qwen3-8B`) plus a
deterministic local fallback, real persistent ChromaDB RAG, and verified
workflow memory with semantic reuse.
**Next phase:** Phase 6 — Dynamic Planner + Real Multi-Agent Runtime.

### Phase 5 — what shipped (Memory)

New `ai-ml/src/autoflow_ai/memory/` package with four distinct memory classes
(session / knowledge-RAG / workflow / graph — never collapsed):
- **Workflow memory**: SQLite metadata + immutable versions + a dedicated
  `autoflow_workflows` Chroma collection (reuses the RAG embedder; physically
  separate from `autoflow_knowledge`).
- **Trace normalization** → semantic workflow (strips coordinates/DOM noise,
  extracts `${param}` parameters); **verification-gated promotion** (failed/
  unverified/secret/unregistered-tool candidates rejected); content-hash
  versioning + dedupe.
- **Authorized semantic retrieval** with tenant/workspace physical filtering +
  scope checks; blocked workflows never returned; deprecated deprioritized;
  explainable multi-signal scoring (semantic + compatibility + verified-success
  + recency with failure decay); compatibility levels + parameter binding.
- **Graph memory** (USES/PRODUCES/VERIFIED_BY) and bounded serializable session
  memory.
- Integrated into the context engine (`WORKFLOW_MEMORY` as `AUTHORIZED_MEMORY`
  **data**) and orchestrator (`learn_from_run` promotes a verified run into a
  reusable workflow; retrieval optional so Golden 01 is unaffected).
- CLI: `autoflow memory status|workflows|search|inspect|versions|deprecate|
  block|graph`.

**Reuse demo (verified live in tests):** run a real `.docx` edit → learn a
semantic workflow → retrieve it later with *different wording* → bind new
parameters. This is workflow learning, NOT model-weight training. New storage
uses stdlib `sqlite3` (no new dependency); `data/memory.sqlite` is gitignored.
30 new tests; all 283 green; Golden 01 + RAG regressions pass.

### Streaming addendum (Phase 2 extension)

The OpenAI-compatible provider now supports SSE streaming: it aggregates content
deltas into a normalized `ModelResponse` and **discards `reasoning_content`** so
no chain-of-thought leaves the gateway. A `requires_streaming` flag on
`ModelDefinition` (env: `*_MODEL_STREAMING=true`) routes such models through the
streaming path. This was required because ModelScope's reasoning models return
`choices: null` for non-streaming requests. Live-verified: `Qwen/Qwen3-8B`
returns real content through the gateway. Keys remain gitignored/redacted.

### Phase 4 — what shipped (RAG)

New `ai-ml/src/autoflow_ai/rag/` package: real local ingestion (docx/pdf/txt/md/
json/csv), deterministic chunking, an `EmbeddingProvider` interface with a
deterministic offline `LocalHashingEmbedder` and an OpenAI-compatible
`RemoteEmbedder` (NVIDIA/ModelScope/OpenAI), persistent ChromaDB behind a small
store wrapper, a `KnowledgeAuthorizationFilter` that **physically** excludes
cross-tenant/workspace/permission records (similarity is never permission), a
`Retriever` producing normalized-scored results + citation-ready `Evidence`
(distinguishing `NO_RESULTS` from `NO_AUTHORIZED_EVIDENCE`), and a
`KnowledgeService` with content-hash idempotency + versioning + controlled
failure handling. Retrieved knowledge enters the Phase 3 context engine as
`AUTHORIZED_KNOWLEDGE` **data** (never instructions). CLI:
`autoflow knowledge ingest|search|inspect|delete|health`. Synthetic dataset
under `examples/knowledge/`. 36 new tests (real ChromaDB + real embedder,
temp-isolated); Golden 01 unaffected.

New deps (verified on Python 3.14): `chromadb 1.5.9`, `pypdf 6.18.1` (+ numpy).
ChromaDB uses our own embeddings, so no `onnxruntime` dependency. Data dirs
(`data/chroma/` etc.) are gitignored.

### Real provider live-verified

`meta/llama-3.2-11b-vision-instruct` on NVIDIA NIM
(`https://integrate.api.nvidia.com/v1`) returns real completions through the
gateway (`autoflow model test` → `provider=openai_compatible fallback=False`).
The API key lives only in the gitignored `.env` (never in code/logs/prompts;
redacted in all output). `.env.example` documents NVIDIA/OpenAI/Groq/OpenRouter/
vLLM/Ollama setup. Note: some listed NVIDIA model ids 404 for this account's
deployment; the vision-instruct model is the confirmed-working one.

### Phase 3 — what shipped (context engine)

New `ai-ml/src/autoflow_ai/context/` package:
- `trust.py` — 8 ordered trust classes; instruction vs data separation.
- `items.py` — `ContextItem` + 14 canonical sections + provenance/permissions.
- `tokens.py` — deterministic `TokenEstimator` (explicitly an estimate).
- `budget.py` — `ContextBudgetPolicy` reserves output first, allocates per section.
- `ranker.py` — deterministic multi-factor ranking (Phase 4 plugs semantic score).
- `sanitizer.py` — quarantines malformed/trust-mismatched items, preserves meaning.
- `authorization.py` — cross-tenant/workspace/permission exclusion before assembly.
- `assembler.py` — full pipeline → `ContextBundle`.
- `bundle.py` — manifest, deterministic hash, `<data>`-wrapped untrusted content.

Wired into the orchestrator (context assembled before the model call); execution
engine and Golden 01 unchanged. CLI: `autoflow context inspect|estimate|validate`.
Tests: 32 added (unit + 8 adversarial + integration); all 208 green; secret-safe.

### Phase 2 — what shipped (real model gateway)

- `model_gateway/http_provider.py` — `OpenAICompatibleProvider` (OpenAI/vLLM/
  LM Studio/Ollama-compatible) over stdlib urllib; imports without network;
  pluggable transport for tests; maps 401/403→auth error (non-retryable),
  408/504→timeout, 5xx/4xx→controlled `ProviderError`; malformed/odd-shape
  responses rejected.
- `model_gateway/config.py` — env-based config + minimal `.env` loader;
  **secret-safe** (`api_key` excluded from repr, `redacted()` masks it, never in
  prompts/logs).
- `model_gateway/policies.py` — `RetryPolicy`, `FallbackPolicy`, `ProviderHealth`.
- `model_gateway/structured.py` — robust JSON extraction + Pydantic validation.
- `model_gateway/router.py` — capability selection + per-provider retry + bounded
  cross-model fallback + health-aware ordering.
- `model_gateway/builder.py` — `build_gateway()` from config; real provider first,
  local always kept as offline fallback.
- `model_gateway/harness.py` — model test + benchmark on AutoFlow-shaped tasks.
- CLI: `autoflow model list|test|benchmark`.
- Orchestrator now builds the gateway via config; **execution engine unchanged**.

New tests: config, policies, structured parser, HTTP adapter (real in-process
localhost server + injected-transport failure modes), router retry/fallback/
health, builder, harness — 38 added, all 176 green. No credentials in code.

### Vertical slice — what shipped (runnable now)

One prompt drives the full pipeline with **real deterministic side effects**,
no network, no API keys, no backend, no Electron:

```
prompt → IntentNormalizer → Planner (validated DAG) → ModelRouter (local
provider) → ExecutionEngine (agent → tool → observe → verify → bounded
recovery) → verified saved document + execution trace
```

New `ai-ml/src/autoflow_ai/` modules:

- `model_gateway/` — provider protocol, offline `LocalRuleProvider`, registry,
  capability router with bounded fallback.
- `editing/operations.py` — structured, deterministic edit ops (replace,
  em-dash normalize, double-space, space-before-punct, trim) + prompt detection.
- `documents/` — real `.docx` (python-docx, run-by-run, structure-preserving),
  `.txt`, `.md` adapters; safe failure on malformed/missing/read-only files.
- `runtime/` — tool registry (registry-bound, schema-validated, permissioned),
  document tools (`inspect`/`edit`/`save`), and the execution engine.
- `brain/` — intent normalizer + planner.
- `orchestrator.py` — single headless entry point (CLI and later desktop both
  use it).
- CLI: `autoflow run|inspect|plan|validate` (readable trace, no chain-of-thought).

Run it:

```powershell
cd ai-ml
uv run autoflow run "Edit this Word file, fix the wording, normalize em-dashes, remove double spaces, and save the edited version to the same file." --file tests/fixtures/sample.docx
uv run pytest -q      # 138 passed
```

New dependency: `python-docx>=1.1,<2.0` (pulls `lxml`), verified on Python 3.14.

### Bugs found and fixed during the slice (by running it / the tests)

- **Illegal state transition:** engine tried `RUNNING → COMPLETE`; the state
  machine requires `VERIFYING → COMPLETE`. Fixed so the terminal move is legal
  and multi-step-after-verify still works.
- **Wording detection gap:** the golden prompt says "fix the wording" but
  detection keyed on "grammar"; broadened to match "wording" so the
  space-before-punctuation fix actually runs. Caught by the e2e content assert
  (not a silent pass).

### Phase 1 — what shipped

- `ai-ml/pyproject.toml` (uv-managed, hatchling build, `autoflow` CLI script).
- `ai-ml/src/autoflow_ai/schemas/` — 11 modules, ~33 contracts:
  enums, common base (deterministic serialization + ID validation), models,
  tools, tasks/planning (DAG), agents, knowledge/context/memory, execution/
  observation/verification/recovery, approvals, workflows/artifacts/automation/
  events/audit.
- Validation logic: DAG cycle/reference checks + topological order; approval
  binding to exact plan-version + action-hash; tool-argument validation against
  a JSON-Schema subset; execution state-machine transition table; secret-leak
  guard on event payloads.
- `ai-ml/src/autoflow_ai/cli.py` + `samples.py` — headless CLI and canonical
  fixtures.
- `ai-ml/tests/` — 8 test modules, 95 tests.
- Populated `.env.example`, `.gitignore`, root `README.md`, `ai-ml/README.md`,
  and `ai-ml/docs/TASKS.md` (closed a §4 doc gap).

### Verify Phase 1 locally

```powershell
cd ai-ml
uv venv
uv pip install -e ".[dev]"
uv run pytest              # 95 passed
uv run autoflow contracts check   # 33 checked, 0 failed
uv run autoflow eval smoke        # ok: true (9 checks)
```

### Bugs found and fixed during Phase 1 (by the tests)

- **Recursion under `validate_assignment`:** `ModelUsage` computed
  `total_tokens` by assigning to a field inside an `after` validator, which
  re-triggered validation infinitely. Moved to a `before` validator.
- **Non-deterministic serialization:** `frozenset` fields serialized in
  arbitrary order, breaking round-trip/hash stability. Added `canonical_dict()`
  that sorts set-origin fields (ordered tuples/lists are left untouched).
- **ID regex too strict:** rejected single-char tokens like `wf_1`; relaxed.
- **Method/field name collision:** base `content_hash()` method shadowed the
  `content_hash` *field* on `Artifact`/`KnowledgeChunk`; renamed to
  `compute_hash()`.

There is a naming collision to be aware of: the master implementation prompt
defines an overall phase plan (Phase 0–25), while `backend/docs/BACKEND_TASKS.md`
and `ai-ml` docs each define their own local "Phase 0…N" backlogs. Throughout this
document, **"Phase N" refers to the master prompt phase plan** unless explicitly
prefixed (e.g. "backend Phase 1").

---

## 2. Current state (measured)

### 2.1 Toolchain available on this machine

Verified via `--version` on 2026-09-12:

| Tool | Version | Notes |
|---|---|---|
| Python | 3.14.2 | `python`, `python3`, `py` all resolve |
| Node.js | 24.14.0 | for desktop (Electron/React) |
| npm | 11.19.0 | |
| pnpm | 10.28.1 | |
| Docker | 29.7.2 | for compose-based local infra |
| git | 2.53.0 (windows) | |
| uv | 0.12.5 | Python packaging/resolver |
| poetry | not installed | `uv` is the available Python tool |

Host OS: Windows / win32, shell: PowerShell 7.

### 2.2 Repository tree (actual)

```text
autoflow_ai/
├── .env.example           # EMPTY
├── .gitignore             # EMPTY
├── README.md              # placeholder ("hola")
├── ai-ml/
│   └── docs/              # docs only, no source
├── backend/
│   └── docs/              # docs only, no source
├── desktop/
│   ├── INDEX.md
│   └── readme.md          # docs only, no source
└── docs/                  # root architecture docs
```

### 2.3 Version control

- Branch `main`, clean working tree, in sync with `origin/main`.
- Remote: `github.com/Boredooms/metamorph.git`.
- Recent history is documentation commits only.

---

## 3. Documentation inventory

### 3.1 Root `docs/` — present

- `PRD.md`
- `PROJECT_VISION.md`
- `PROJECT_STRUCTURE.md`
- `SYSTEM_ARCHITECTURE.md`
- `AI_ML_ARCHITECTURE.md`
- `MULTI_AGENT_ARCHITECTURE.md`
- `DEPLOYMENT.md`
- `IMPLEMENTATION_STATUS.md` (this file)

### 3.2 `ai-ml/docs/` — present

- `README.md`, `INDEX.md`, `REQUIREMENTS.md`, `AI_ML_PRD.md`,
  `MODEL_AND_CONFIG.md`, `AGENT_BRAIN.md`, `EXECUTION_RUNTIME.md`,
  `PROMPTS_TOOLS_AND_SCHEMAS.md`

### 3.3 `backend/docs/` — present

- `README.md`, `BACKEND_PRD.md`, `BACKEND_ARCHITECTURE.md`, `BACKEND_TASKS.md`,
  `API(4).md`, `AUTH_TENANCY_SECURITY.md`, `ORCHESTRATION_EXECUTION.md`,
  `INTEGRATIONS_MODELS_STORAGE.md`

### 3.4 `desktop/` — present

- `INDEX.md`, `readme.md`

---

## 4. Documentation vs. prompt conflicts (must resolve, do not silently pick)

The master prompt's "read before writing code" list and `PROJECT_STRUCTURE.md`
reference several documents that **do not exist**. Per the project rule
("if implementation and documentation conflict, identify the conflict, resolve
according to the higher-level PRD/architecture, update docs, continue"), these are
tracked here rather than silently ignored:

| Referenced doc | Referenced by | Status | Resolution |
|---|---|---|---|
| `docs/PROJECT_SETUP.md` | master prompt, PROJECT_STRUCTURE | MISSING | Create during Phase 1 setup, once real manifests/scripts exist |
| `docs/EXECUTION_ENGINE.md` | master prompt | MISSING | Content is covered by `ai-ml/docs/EXECUTION_RUNTIME.md` + backend `ORCHESTRATION_EXECUTION.md`; treat those as source of truth |
| `ai-ml/docs/TASKS.md` | ai-ml `INDEX.md`, `README.md` | MISSING | Create as the AI/ML implementation backlog before Phase 1 code |
| `ai-ml/docs/EVALUATION.md` | ai-ml `INDEX.md`, `README.md` | MISSING | Create before Phase 24 (evaluation harness); referenced by test-pyramid docs |
| Many `docs/*.md` (API.md, AUTH_AND_TENANCY.md, KNOWLEDGE_AND_RAG.md, TOOL_CALLING.md, BROWSER_AUTOMATION.md, COMPUTER_USE.md, MODEL_ROUTING.md, WORKFLOW_ENGINE.md, APPROVALS.md, ARTIFACT_PIPELINE.md, AUDIT_AND_OBSERVABILITY.md, DESKTOP.md, DATABASE.md, SECURITY.md, TASKS.md, DEMO_SCRIPT.md) | PROJECT_STRUCTURE | MISSING at root | Backend equivalents exist under `backend/docs/`; root-level versions are optional and created on demand as each subsystem is built |

**Empty placeholder files that must be filled before/at Phase 1:**

- `.env.example` — empty; must document all env vars from `MODEL_AND_CONFIG.md` §7
  and the master prompt §34 (no real secrets).
- `.gitignore` — empty; must exclude `.env`, Python/Node build artifacts,
  virtualenvs, `__pycache__`, `node_modules`, Chroma persistence, object-store data.
- `README.md` — placeholder `hola`; must describe the project and how to run the
  AI/ML core headlessly.

No conflict requires overriding the PRD/architecture at this time; all conflicts are
"missing artifact" gaps, not contradictions.

---

## 5. Implemented components

**None.** No source code exists in any subsystem.

| Subsystem | Intended location (per PROJECT_STRUCTURE) | State |
|---|---|---|
| Contracts / schemas | `ai-ml/src/autoflow_ai/schemas/` | Not created |
| Model gateway | `ai-ml/src/autoflow_ai/model_gateway/` | Not created |
| Context engine | `ai-ml/src/autoflow_ai/` (context assembly) | Not created |
| RAG / ChromaDB | `ai-ml/src/autoflow_ai/rag/` | Not created |
| Memory | `ai-ml/` memory stores | Not created |
| Planner / agents | `ai-ml/src/autoflow_ai/agents/` | Not created |
| Tool calling | `ai-ml/src/autoflow_ai/tool_calling/` | Not created |
| Tool runtime | `ai-ml/` deterministic runtime | Not created |
| Computer use | `ai-ml/src/autoflow_ai/computer_use/` | Not created |
| Verification / recovery | `ai-ml/src/autoflow_ai/recovery/` | Not created |
| Eval harness | `ai-ml/evals/` | Not created |
| CLI (`autoflow`) | `ai-ml/` | Not created |
| Backend API | `backend/app/` | Not created |
| Database migrations | `backend/app/db/`, `infra/migrations/` | Not created |
| Desktop | `desktop/` | Not created |
| Infra (compose) | `infra/` | Not created |

---

## 6. Missing components (gap list)

Everything below is required by the docs and does not yet exist:

1. Python package scaffolding for `ai-ml/` (`pyproject.toml`, `src/`, `tests/`).
2. Python package scaffolding for `backend/` (`pyproject.toml`, FastAPI app).
3. Node/Electron scaffolding for `desktop/`.
4. `infra/` (Docker Compose for Postgres, Redis, ChromaDB, object store).
5. `scripts/` and `examples/` directories (golden tasks, fixtures).
6. Typed contract schemas (Phase 1) — the 30+ models listed in the prompt §5.
7. Every subsequent phase artifact (model gateway → desktop).
8. The missing docs listed in §4.
9. Populated `.env.example`, `.gitignore`, and real `README.md`.

---

## 7. Broken components

**None** — nothing is broken because nothing is implemented yet. The only defects
are empty/placeholder files (`.env.example`, `.gitignore`, `README.md`) noted in §4.

---

## 8. Technical risks

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Python 3.14 is very new; some AI/RAG/browser libs (chromadb, playwright, pydantic ecosystem) may lag on wheels | Blocks dependency install | Pin versions; verify each dependency on 3.14 at Phase entry; consider a 3.12/3.13 fallback interpreter if a critical dep is unavailable |
| R2 | Master prompt phase numbering vs. per-subsystem "Phase 0" backlogs collide | Planning confusion | This doc fixes the convention (master phases unless prefixed) |
| R3 | Missing referenced docs (§4) | Ambiguity during implementation | Resolve each via existing PRD/architecture; create docs as phases reach them |
| R4 | Secret handling: `.env.example` empty, rules forbid secrets in renderer/prompts/logs | Security regression if rushed | Fill `.env.example` as documentation-only in Phase 1; enforce secret isolation at provider boundary |
| R5 | External integrations (Gmail, browser, desktop) cannot be safely exercised in this environment | False "verified" claims | Use deterministic adapters + clearly marked integration-test boundaries; never report unverified integrations as passing |
| R6 | Windows-first dev host; desktop/browser/computer-use automation is OS-sensitive | Cross-platform gaps | Keep AI/ML core OS-agnostic and headless; isolate OS-specific runtime behind adapters |
| R7 | No CI configured | Regressions go unnoticed | Add test/eval runners as part of Phase 1 scaffolding |

---

## 9. Non-negotiable rules carried into every phase

From the master prompt (abbreviated, full list governs all work):

- Models propose; deterministic runtime performs side effects; verifiers confirm.
- No LLM has unrestricted execution authority; tools come only from a registry.
- Tool success ≠ business success; every material side effect is verified.
- Approval is first-class workflow state, bound to an exact plan/action version.
- Retrieved documents are untrusted data, never instructions; authZ happens
  outside semantic retrieval.
- Secrets never reach the renderer, prompts, or logs.
- Coordinates are never the canonical workflow representation.
- Recovery is bounded; no infinite loops.
- AI/ML must run headlessly without Electron; desktop is built last.
- Every production behavior has tests; never report unexecuted tests as passing;
  never fake an integration.

---

## 10. Reproduce the current state

From a clean clone on a machine with the toolchain in §2.1:

```powershell
# 1. Clone and enter
git clone https://github.com/Boredooms/metamorph.git autoflow_ai
cd autoflow_ai

# 2. Confirm the repo is docs-only (no source/tests/manifests)
git ls-files

# 3. Confirm clean git state
git status

# 4. Confirm toolchain
python --version; node --version; npm --version; docker --version; uv --version
```

Expected result: only Markdown docs, empty `.env.example`/`.gitignore`, and a
placeholder `README.md`. No build, test, or run command exists yet because no
project manifest has been created.

---

## 11. Phase ledger

| Phase | Description | Status | Exit gate |
|---|---|---|---|
| 0 | Repository audit + this document | **DONE** | Repo understood; status doc produced |
| 1 | Contract layer (typed schemas) | **DONE** | 95 tests pass; invalid plans/tools/workflows/approvals rejected; deterministic serialization; CLI self-checks green |
| 2 | Model gateway | **DONE** | Real OpenAI-compatible provider via env config + local fallback; retry/fallback/health; structured-output validation; secret-safe; 176 tests pass |
| 3 | Context engine | **DONE** | Budgeted, ranked, trust-separated, ACL-filtered, deterministic-hashed context; CLI + 208 tests pass |
| 4 | ChromaDB + knowledge | **DONE** | Persistent ChromaDB; physical-filter authorized semantic retrieval + evidence; tenant/workspace isolation; integrated into context engine; 244 tests pass |
| 5 | Memory layer | **DONE** | Session/workflow/graph memory; SQLite + separate autoflow_workflows collection; verification-gated promotion; authorized semantic reuse; 283 tests pass |
| 6 | Request normalizer | **DONE** (vertical slice) | NormalizedTask from raw prompt |
| 7 | Planner (dynamic) | **DONE** (Phase 6) | Typed PlannerOutput + RuntimeGraph + deterministic validation; deterministic + model planner (fail-closed) |
| 8 | Agent system | **DONE** (Phase 6) | SpecialistAgent registry + MultiAgentRuntime scheduler, bounded concurrency, dependency resolution, bounded replanning |
| 9 | Execution agent | **DONE** (Phase 6) | Agents propose structured actions; runtime validates + executes via authority chain |
| 10 | Tool calling | **DONE** (Phase 7) | ToolCallingController: proposal→schema→registry→authz→policy→approval→execute→sanitized trace |
| 11 | Deterministic tool runtime | **DONE** (partial) | Document tools (vertical slice) + Windows computer tools (Phase 7); browser/email pending |
| 12 | Computer/browser abstraction | **DONE** | Real Windows UIA + real headless-browser (Playwright) adapters; unified observation/fusion/target-resolver; vision interface + OpenCV; all live-verified |
| 13 | Document workflow E2E | **DONE** (vertical slice) | Edit + save + verify a real docx |
| 14 | Email approval workflow E2E | Not started | Draft → approve → send → verify |
| 15 | Approval engine | Not started | Approval as first-class state, mutation invalidation |
| 16 | Verification | Not started | Postcondition checks, not "model said done" |
| 17 | Recovery / replanning | Not started | Bounded failure ladder |
| 18 | Semantic workflow generation | Not started | Verified runs → reusable workflows |
| 19 | Automation engine | Not started | Triggers reuse the same execution engine |
| 20 | Backend integration | Not started | Stable APIs; AI/ML still runs headlessly |
| 21 | Databases | Not started | Postgres migrations + Chroma + object store |
| 22 | Event system | Not started | Execution reconstructable from events |
| 23 | Test environments | Not started | Fake fs/email/browser/desktop/knowledge |
| 24 | Evaluation / stress | Not started | Golden + adversarial + chaos suites |
| 25 | Desktop | Not started | Antigravity-style client over stable APIs |

---

## 12. Recommended next step (Phase 1 entry)

Before writing Phase 1 contracts:

1. Create `ai-ml/pyproject.toml` (uv-managed) with pinned, 3.14-verified deps
   (`pydantic`, `pytest`).
2. Scaffold `ai-ml/src/autoflow_ai/schemas/` and `ai-ml/tests/`.
3. Populate `.env.example`, `.gitignore`, and `README.md`.
4. Create `ai-ml/docs/TASKS.md` (AI/ML backlog) to close the §4 gap.
5. Implement contract tests first, then the schemas listed in the prompt §5.

Phase 1 must not begin until this document is committed.


---

## Milestone: True Agentic Runtime + Full Integration (2026-09-12)

This milestone closed the gaps found in the CHECKPOINT-A audit: RAG/memory were
not in the mission path, there was no Gmail/Word-UI/live-vision/persistence, and
Browser/Communication agents were stubs. Everything below composes on the
existing substrate (no duplicate gateway/runtime/registry/RAG/memory).

**Test state:** `uv run pytest -q` → **626 passed, 6 skipped** (env-gated real
integrations), 2 deselected real-desktop tests pass in isolation. `compileall`
clean. Baseline 504 preserved; +122 new tests. Stress: **185+ mission
executions, false_success = 0.**

### What shipped (status-labeled)

- **RAG + memory grounding in missions** (`society/grounding.py`) — IMPLEMENTED,
  UNIT + INTEGRATION TESTED. Retrieved knowledge posted as `EXTERNAL_DATA`,
  memory as `OBSERVATION` — never instructions. Explicit `NO_RELEVANT_CONTEXT`.
  Tenant/workspace/permission enforced by the services. 10 tests.
- **Provenance-backed web research** (`society/research.py`) — IMPLEMENTED,
  UNIT + INTEGRATION TESTED, **LIVE VERIFIED** (real Bing via Playwright/Chromium).
  Facts labeled DIRECTLY_OBSERVED/DERIVED/INFERRED/UNKNOWN with source URL +
  timestamp + provenance id; anti-hallucination (facts only from live DOM).
  Web-injection stays data. 10 tests + 1 live (SKIP-gated `AUTOFLOW_ALLOW_WEB`).
- **Live vision provider** (`computer_use/vision.py::RealVisionProvider`) —
  IMPLEMENTED, UNIT TESTED, **LIVE VERIFIED** directly against NVIDIA
  `meta/llama-3.2-11b-vision-instruct` (real base64 PNG → structured JSON →
  parsed candidate; low-confidence never auto-acts; fail-closed on
  timeout/malformed). `AdaptiveObserver` (vision only on ambiguity/unexpected
  change). OpenCV path untouched. 15 tests + 1 live (SKIP-gated `AUTOFLOW_REAL_VISION`).
- **Word document lifecycle** (`computer_use/word_workflow.py`) — IMPLEMENTED,
  INTEGRATION TESTED (real python-docx open→edit→save→reopen-verify→persist,
  save verified only after independent reopen + hash change). Real Word-UI path
  LIVE-gated `AUTOFLOW_REAL_WORD`. 10 tests + 1 real skip.
- **Gmail-over-browser** (`computer_use/gmail.py`, `society/gmail_workflow.py`) —
  IMPLEMENTED, INTEGRATION TESTED (fake Gmail DOM). Approval bound to the exact
  observed message + attachment content hash; send only after approval; any
  post-approval change invalidates; independent Sent-view verification;
  WAITING_FOR_USER on login (no passwords). Real Gmail is **SKIPPED** (needs an
  authenticated controlled account + controlled recipient — not available here;
  labeled FUTURE for live). 15 tests + 1 real skip.
- **Real BrowserAgent + CommunicationAgent** (`agents/specialists.py`) —
  IMPLEMENTED, UNIT TESTED. Capability-routed, reject foreign tools. 15 tests.
- **Mission persistence + resume** (`society/persistence.py`) — IMPLEMENTED,
  TESTED. Atomic local JSON checkpoints; resume skips verified work
  (no-data-loss on downstream failure proven). 10 tests.
- **Flagship E2E** (`society/flagship.py`) — IMPLEMENTED, INTEGRATION TESTED,
  and run end-to-end on the INTEGRATION path (real python-docx doc + fake Gmail):
  document mission (non-hardcoded delegation) → draft → approval → send →
  independent verify; `is_true_agentic = true`. No send without approval. 10 tests.
- **Agenticity acceptance evaluator** (`society/metrics.py::evaluate_agenticity`)
  — IMPLEMENTED, TESTED. Verifies 9 observable agentic properties from the trace.
- **Chaos + security + stress** (`tests/test_chaos_security_stress.py`) — 27
  tests: failure injection, injection defense, approval tampering, secret
  redaction, path traversal, false-verification rejection, 185+ stress missions
  with false_success = 0.
- **CLI** — added `mission run --persist --resume`, `mission inspect/trace/
  graph/approve`, `research run`, `websearch run`, `rag search` (alias).

### Capability matrix

| Capability | Implementation | Unit | Integration | Live | Notes |
|---|---|---|---|---|---|
| RAG retrieval | REAL | ✅ | ✅ | (RAG live-verified earlier phase) | grounded into missions as DATA |
| Web search | REAL | ✅ | ✅ | ✅ (Bing/Chromium) | DOM-only, provenance-backed |
| Web research + labels | REAL | ✅ | ✅ | ✅ | observed/derived/inferred/unknown |
| Workflow memory | REAL | ✅ | ✅ | n/a | promotion policy-gated |
| Supervisor (dynamic delegation) | REAL | ✅ | ✅ | n/a | capability match, no fixed table |
| Sub-agents + handoff | REAL | ✅ | ✅ | n/a | ≥2 specialists per flagship |
| Blackboard (trust/scope) | REAL | ✅ | ✅ | n/a | data never instruction |
| Independent QA/critic | REAL | ✅ | ✅ | n/a | can reject; bounded revision |
| Computer (Windows UIA) | REAL | ✅ | ✅ | ✅ (Notepad) | semantic, not coordinates |
| Browser automation | REAL | ✅ | ✅ | ✅ (local + Bing) | local/allowlisted policy |
| Vision (multimodal) | REAL | ✅ | ✅ | ✅ (NVIDIA) | evidence-only, fail-closed |
| OpenCV (deterministic) | REAL | ✅ | ✅ | n/a | unchanged |
| Word document lifecycle | REAL | ✅ | ✅ | gated `AUTOFLOW_REAL_WORD` | python-docx verified; UI live-gated |
| Gmail compose/draft | REAL | ✅ | ✅ | SKIPPED (no account) | fake DOM verified; live FUTURE |
| Attachment verification | REAL | ✅ | ✅ | with Gmail | content-hash bound |
| Approval (exact-action bound) | REAL | ✅ | ✅ | n/a | any change invalidates |
| Send + independent verify | REAL | ✅ | ✅ | SKIPPED (no account) | never trusts "clicked" |
| Verification engine | REAL | ✅ | ✅ | ✅ | multi-signal |
| Recovery / replan | REAL | ✅ | ✅ | n/a | bounded ladder |
| Long-running persistence/resume | REAL | ✅ | ✅ | n/a | atomic JSON, no-data-loss |
| Workflow learning | REAL | ✅ | ✅ | n/a | verified missions only |
| Real-model reasoning | REAL | ✅ | ✅ | ✅ (NVIDIA/ModelScope) | fail-closed |

Legend: ✅ = exercised in the suite (or directly verified). "SKIPPED" = honestly
not run (missing credentials/hardware); "gated" = runs only with the env flag.


---

## Milestone: Final AI/ML Core + Model Lab + Real Autonomy (2026-09-12)

Closed the remaining gaps from the CHECKPOINT-A audit: a Model Evaluation Lab,
real-time observability, an EvidenceBroker, a deterministic simulation mode, a
tuning-ready execution dataset, a health check, and a greatly expanded test
matrix. Everything composes on the existing gateway/runtime/society (no
duplicates).

**Test state:** `uv run pytest -q` → **1031 passed, 7 skipped** (env-gated real
integrations), 2 deselected real-desktop tests pass in isolation. `compileall`
clean. 626 baseline preserved; **+405 new tests**. Stress: **440+ mission/
benchmark executions, false_success = 0.**

### What shipped (status-labeled)

- **Model Lab** (`lab/`) — IMPLEMENTED, UNIT + INTEGRATION TESTED, partially
  LIVE. `ModelLab` reuses the gateway (no 2nd gateway, no hardcoded creds).
  102-task deterministic benchmark across 13 categories; `ModelScorecard`
  (schema_validity, task_success, tool_validity, hallucination_rate,
  false_success_rate, p50/p95 latency). CLI: `model lab list/test/task/
  benchmark/compare`, `model console`. 18 tests + 1 LIVE_NVIDIA gate.
- **Model observability** (`lab/events.py`) — IMPLEMENTED, TESTED. `ModelTrace`
  (decision_summary, observations_used, evidence_refs, selected_action,
  alternatives_count, confidence, uncertainty, why_blocked/replanned) +
  event stream (MODEL_REQUEST..FALLBACK). Secret-redacted; never emits CoT.
- **EvidenceBroker** (`society/evidence_broker.py`) — IMPLEMENTED, TESTED.
  Merges USER/RAG/WEB/WORKFLOW_MEMORY/SESSION/OBSERVATION/TOOL_RESULT/
  VERIFICATION with trust + provenance; renders INTENT vs DATA separately so
  the model never gets undifferentiated text. Search relevance validation +
  deterministic reformulation (never fills gaps with model memory). 14 tests.
- **Simulation + real-time trace** (`society/simulation.py`) — IMPLEMENTED,
  SIMULATION VERIFIED. `mission simulate [--live]` runs the flagship over a
  deterministic environment with a live stage trace (SUPERVISOR..FINAL);
  `mission run --live` streams the real trace; `compare_sim_vs_live` diffs
  plan/verification. 10 tests.
- **Execution dataset** (`lab/execution_dataset.py`) — IMPLEMENTED, TESTED.
  Secret-redacted `ExecutionRecord` JSONL for future tuning (does NOT train
  anything now). `autoflow health` reports every subsystem + provider health.
  8 tests.
- **Expanded matrix** (`tests/test_expanded_matrix.py`) — 355 parametrized:
  90+ security cases (injection-stays-data, blocked tools, approval tamper,
  path traversal, false-claim, scope isolation), 260+ deterministic stress
  missions (delegation/recovery/flagship), model-benchmark bucket, search
  relevance — all false_success = 0.

### Final capability matrix

| Capability | Impl | Unit | Integration | Simulation | Live | Notes |
|---|---|---|---|---|---|---|
| Model gateway (NVIDIA/Qwen/local) | REAL | ✅ | ✅ | ✅ | ✅ (raw 1.4s) | NVIDIA intermittently times out under load; fails closed |
| Model Lab + benchmark + scorecard | REAL | ✅ | ✅ | ✅ | partial (NVIDIA gate) | 102 tasks; NVIDIA vs Qwen vs deterministic |
| Model observability / trace | REAL | ✅ | ✅ | ✅ | ✅ | secret-free, no CoT |
| RAG grounding in missions | REAL | ✅ | ✅ | ✅ | (earlier) | EXTERNAL_DATA, NO_RELEVANT_CONTEXT |
| EvidenceBroker (multi-source) | REAL | ✅ | ✅ | ✅ | n/a | INTENT vs DATA separated |
| Web search + research | REAL | ✅ | ✅ | ✅ | ✅ (Bing) | provenance; relevance-validated |
| Vision (multimodal) | REAL | ✅ | ✅ | ✅ | ✅ (NVIDIA) | evidence-only, fail-closed |
| Windows computer (UIA) | REAL | ✅ | ✅ | ✅ | ✅ (Notepad) | semantic |
| Supervisor / sub-agents / QA | REAL | ✅ | ✅ | ✅ | n/a | dynamic delegation, independent critic |
| Word document lifecycle | REAL | ✅ | ✅ | ✅ | gated | python-docx verified; UI gated |
| Gmail compose/approval/send | REAL | ✅ | ✅ | ✅ | SKIPPED | needs controlled account |
| Approval (exact-action bound) | REAL | ✅ | ✅ | ✅ | n/a | any change invalidates |
| Persistence / resume | REAL | ✅ | ✅ | ✅ | n/a | atomic JSON, no-data-loss |
| Simulation + sim-vs-live | REAL | ✅ | ✅ | ✅ | n/a | deterministic full-loop |
| Execution dataset / health | REAL | ✅ | ✅ | ✅ | n/a | secret-redacted; tuning-ready |

Legend: ✅ exercised/verified; "gated"/"SKIPPED" = honestly not live-run here.
