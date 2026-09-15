# AutoFlow AI — Integration Audit

**Status:** Phase 1 (audit) — no code changed yet.
**Author:** integration pass.
**Purpose:** inspect the three existing systems, map responsibilities/contracts/
events/state, find mismatches, and define the exact adapter + sequence to make
`Electron → Control Plane → REAL AI/ML → safe tools → REAL verification → Control
Plane → SSE → Electron` work — without rebuilding any system.

---

## 1. Current architecture (as-built, verified on disk)

Three real systems exist under `metamorph/`:

```text
desktop/   Electron + Next.js command center           (built, typechecks, packaged)
backend/   FastAPI control plane                        (built, 35 tests pass, 38 endpoints)
ai-ml/     Real AI/ML runtime (autoflow_ai package)     (built, ~380–1068 tests, CLI + HTTP server)
```

Today they are **not connected to each other**:

- Desktop runs on local mock data by default; it has a `backendRepository` +
  SSE adapter gated by `NEXT_PUBLIC_API_URL`, but nothing points it at a backend.
- Backend runs fully on **mock** runtimes; `app/runtime.py` raises
  `NotImplementedError` for every `*_MODE=real`.
- AI/ML runs standalone via its own CLI and its own stdlib HTTP server
  (`autoflow_ai.server`, port 8770, `/missions`), driven by
  `AutoFlow.build().run_mission(...)`.

Target architecture (unchanged from the master prompt):

```text
Electron ──REST+SSE──▶ Control Plane (FastAPI) ──internal contract──▶ AI/ML runtime
                          authoritative state                          intelligence
                                                                        + execution + verify
```

### Authoritative-boundary decision

There is **one product-facing backend: `backend/`**. The AI/ML HTTP server
(`ai-ml/server`, port 8770) is **kept** as a standalone dev/eval/research
surface but is **not** on the product path. Product execution goes
`Electron → backend → AI/ML runtime` — and the AI/ML runtime is reached
**in-process as a Python library** (import `autoflow_ai`), not over its HTTP
server, because both are Python and this avoids a second network hop and a
second event system on the product path.

> Note: `ai-ml/AGENT_ONBOARDING.md` says "backend is docs-only; the real API is
> `ai-ml/server`; desktop is a placeholder." That guidance **predates** the
> `backend/` and `desktop/` we built. This audit supersedes it: `backend/` is
> the product control plane; `ai-ml/server` becomes an optional standalone.

---

## 2. Endpoint matrix

| Concern | Backend (`/api/v1`, product) | AI/ML server (`:8770`, dev/eval) |
| --- | --- | --- |
| Create work | `POST /tasks` (idempotent, returns task_id+execution_id, QUEUED) | `POST /missions` `{prompt,mode,model,target_path}` |
| Run | (automatic via worker/queue) | `POST /missions/{id}/run` / `/simulate` |
| Read | `GET /tasks/{id}`, `GET /executions/{id}` | `GET /missions/{id}` |
| Events | `GET /executions/{id}/events?after=`, `/stream` (SSE) | `GET /missions/{id}/events?after=` (SSE), `/trace` |
| Plans | `GET /tasks/{id}/plans[/{version}]` | (plan is internal to mission) |
| Approvals | `GET/POST /approvals/...` (authoritative) | mission emits `approval.requested`; no decision endpoint |
| Artifacts | `GET /artifacts[/{id}][/download]` | `GET /missions/{id}/artifacts` (from events) |
| Registry | `/agents /workflows /knowledge /workspaces` | `/models /capabilities /health` |

**Takeaway:** the backend already owns the product surface the desktop adapter
targets. No third API is needed. The AI/ML server is a superset only for model
lab / capability introspection, which can be surfaced later via backend if wanted.

---

## 3. Contract matrix (the important part)

Concept-by-concept comparison of the three systems. **CP** = Control Plane
(`backend/app/schemas`), **ML** = `ai-ml/src/autoflow_ai/schemas`, **UI** =
`desktop/lib/types.ts`.

| Concept | CP shape | ML shape | UI shape | Mismatch | Canonical / adapter |
| --- | --- | --- | --- | --- | --- |
| **Status enums** | `TaskStatus` UPPERCASE (`QUEUED`,`AWAITING_APPROVAL`,`COMPLETE`…) | `ExecutionStatus` **lowercase** (`queued`,`awaiting_approval`,`complete`…) | UPPERCASE (matches CP) | **Case only** — identical vocabulary | CP UPPERCASE is canonical on the wire. Adapter upper()s ML values. |
| **Step status** | `StepStatus` (WAITING/READY/RUNNING/…/COMPLETE) | `StepStatus` (pending/ready/running/…/complete) | matches CP | case + `WAITING`↔`pending` | Map in adapter. |
| **Risk class** | `RiskClass` UPPER (LOW/MEDIUM/HIGH/CRITICAL) | `RiskClass` lower (low/…/critical) | (uses backend value) | case | upper() in adapter. |
| **Approval status** | PENDING/APPROVED/REJECTED/EXPIRED/**INVALIDATED** | pending/approved/rejected/expired | matches CP | case; ML lacks INVALIDATED | CP authoritative; ML only *recommends* approval. |
| **Verification status** | PASSED/FAILED/PENDING | passed/failed/**inconclusive**/not_run | PASSED/FAILED/PENDING/NONE | case + extra ML values | Map `inconclusive/not_run`→`PENDING`/`NONE`. |
| **Recovery** | `RecoveryDecision` (RETRY/REOBSERVE/RERESOLVE/ALTERNATE_PATH/REPLAN/HUMAN_ESCALATION/FAIL) | `RecoveryStrategy` (retry/re_observe/re_resolve/alternate_path/visual_grounding/replan/human_escalation/abort) | recovery phases only | naming: `REOBSERVE`↔`re_observe`, `FAIL`↔`abort`, ML adds `visual_grounding` | Map in adapter; CP is enforcement authority. |
| **Plan** | `Plan{plan_id,version,graph:{steps[]},plan_hash,...}`; `PlanStepSpec{step_id,index,objective,agent_profile,dependencies,allowed_tools,...}` | `TaskGraph` (planner output → `PlannerOutput.to_runtime_graph`); nodes have agent_type, parameters(incl `tool`), dependencies | UI `TaskStep{id,agentId,dependsOn,tools,...}` | **structural**: ML `TaskGraph`/nodes ≠ CP `PlanStepSpec` | **Adapter maps ML TaskGraph → CP Plan/PlanStepSpec.** CP persists the canonical immutable plan. |
| **Task / mission** | `TaskRequest{workspace_id,goal,constraints,attachments}` | mission = `run_mission(prompt, target_path, use_model)` (no workspace/identity; uses DEFAULT_ORG/WS) | camelCase Task | ML mission has no tenancy/approval object | **Adapter: ControlPlaneTask → MissionRequest(prompt,target_path); CP owns identity/state.** |
| **Agent run** | `AgentRunRequest`/`AgentRunResult` (proposed_actions, observations) | society supervisor runs specialists internally; returns `MissionReport{all_verified,outcome,verified_tasks,failed_tasks}` | n/a | ML doesn't expose per-step `run_step` in the mission path (it's internal to `MissionSupervisor`) | Two integration granularities (see §7). |
| **Tool call** | `ToolCall`/`ToolResult` (backend ToolRuntime) | `ToolDefinition` + `ToolCallingController` authority chain (real) | n/a | **both have tool runtimes** | **Do NOT duplicate.** AI/ML owns real tool execution; CP owns policy/approval gate + persistence. |
| **Verification** | `VerificationResult{status,checks,evidence,confidence}` | real `document.verify` etc.; `MissionReport.all_verified` | UI shows verification badge | ML verification is embedded in the mission | Map ML verified→CP VerificationResult PASSED with evidence. |
| **Event** | `ExecutionEvent{event_id,type(dotted),sequence,...}` persisted+sequenced | `MissionEventBus` events (`EventType` dotted, incremental `event_id`) | UI `ExecutionEvent{id,at,type,label,...}` | **two event systems**; ML `_STAGE_TO_EVENT` names ≠ CP EventType names | **CP is the canonical product event stream.** Adapter translates ML events→CP events (see §5). |
| **Artifact** | `Artifact{kind UPPER, verification_status,...}` persisted | artifact.created event `{name,path}` | UI `Artifact{kind lower,...}` | ML artifact is an event, not a record | Adapter persists ML artifact → CP Artifact; CP is source of truth. |
| **IDs** | `task_/exec_/step_/appr_/evt_/art_` | `exec_`, `mreq_`, mission ids like `exec_exec<ts>` | consumes CP ids | ML invents its own ids | **CP ids are authoritative;** store ML ids as associated metadata. |

**Enum encoding is the single biggest, simplest mismatch: UPPERCASE (CP/UI) vs
lowercase (ML).** One mapping helper resolves ~80% of it.

---

## 4. State-machine matrix

Both define the **same 12 states**. CP `app/orchestration/state_machine.py` is
the single authoritative validator. ML `ExecutionStatus` +
`TERMINAL_EXECUTION_STATES` is a vocabulary, not an enforcement authority in the
mission path (the mission returns a terminal `outcome`).

| State | CP | ML | Note |
| --- | --- | --- | --- |
| QUEUED→PLANNING→VALIDATING→AWAITING_APPROVAL→RUNNING→VERIFYING→RECOVERY→COMPLETE/FAILED/CANCELLED/EXPIRED/BLOCKED | authoritative transitions | same names (lowercase) | **CP enforces; ML informs.** The adapter maps a mission outcome to CP transitions the state machine validates. |

**Rule:** the adapter never sets CP status directly. It reports mission
progress/outcome; CP services call the state machine.

---

## 5. Event matrix + mapping

ML mission events (`MissionEventBus` via `_STAGE_TO_EVENT`) → canonical CP events:

| ML event / stage | CP `EventType` |
| --- | --- |
| `MISSION_STARTED` / supervisor | `execution.started` |
| `PLAN_CREATED` (planner) | `plan.created` (+ `plan.validated` after CP validates) |
| `TASK_DELEGATED` / agent begins | `step.started` |
| `ACTION_PROPOSED` (document/computer/browser) | `tool.requested` → `tool.started` → `tool.completed` |
| `OBSERVATION_CAPTURED` | `observation.created` |
| `VERIFICATION_PASSED` / `VERIFICATION_FAILED` | `verification.passed` / `verification.failed` |
| `APPROVAL_REQUESTED` | `approval.requested` (CP creates the Approval record) |
| `ARTIFACT_CREATED` | `artifact.created` (CP persists Artifact) |
| `MISSION_COMPLETED` | `execution.completed` |
| `MISSION_FAILED` | `execution.failed` |
| recovery stages | `recovery.started` / `recovery.replanned` |

**Electron consumes only the CP stream** (`/executions/{id}/events`). ML events
are internal; the adapter translates the operationally-meaningful ones and the
CP `event_service` assigns the authoritative monotonic sequence. Honesty rule
preserved: `verification.passed` / `execution.completed` are emitted **only**
when the real mission report says verified/complete.

---

## 6. Responsibility matrix (who owns what — no overlap)

| Responsibility | Owner |
| --- | --- |
| identity, auth, RBAC, org/workspace, tenancy | **Control Plane** |
| task/execution durable state + state machine | **Control Plane** |
| plan **persistence** + immutability + versioning + plan_hash | **Control Plane** |
| policy decision + **approval authority** + action-hash binding | **Control Plane** |
| event durability, sequencing, SSE, replay, audit, idempotency, concurrency | **Control Plane** |
| goal understanding, planning, task decomposition, agent assignment | **AI/ML** |
| agent reasoning, model routing, tool **proposal**, context/RAG/memory | **AI/ML** |
| actual tool execution + real side effects (docs, browser, Windows/Needle) | **AI/ML runtime** (do NOT duplicate in CP) |
| postcondition verification / business-outcome truth | **AI/ML verifier** (result recorded by CP) |

---

## 7. Duplicate responsibilities & how to resolve

1. **Two event systems** → keep both; CP is canonical for the product. Adapter
   translates ML→CP. Do not stream ML events to Electron directly.
2. **Two tool runtimes** (CP `MockToolRuntime` vs ML `ToolCallingController` +
   real tools) → **AI/ML owns real execution.** In integration mode CP does not
   execute tools itself; it gates (policy/approval) and records. CP's mock tool
   runtime stays for mock mode.
3. **Two verifiers** (CP `MockVerifier` vs ML real `document.verify`) → AI/ML
   verifies for real; CP records the `VerificationResult` and gates COMPLETE.
4. **Two "orchestrators"** (CP `MockOrchestrator` vs ML `Planner`/society) →
   AI/ML plans; CP validates + persists. CP's mock stays for mock mode.
5. **Two servers** (`backend` FastAPI vs `ai-ml/server`) → backend is product;
   ai-ml server is standalone dev/eval. Not deleted, not on product path.

**No component is deleted or duplicated. The convergence is adapters, not rewrites.**

---

## 8. The one adapter to build (already-prepared seam)

The backend **already** has the exact seam the master prompt asks for:
`backend/app/runtime.py` resolves `*_MODE` (mock/real) into implementations, and
every `real` branch currently raises `NotImplementedError`. The interfaces exist
in `app/orchestration/interfaces.py`, `app/agents/interfaces.py`,
`app/tools/interfaces.py`, `app/verification/interfaces.py`,
`app/recovery/interfaces.py`, `app/policy/interfaces.py`.

**Plan — add an intelligence adapter package (do not touch the mock path):**

```text
backend/app/intelligence/
├── interfaces.py        # IntelligenceRuntime Protocol (plan/run_step/verify/recover)
├── mock_runtime.py      # delegates to existing mock orchestrator/agent/verifier
├── ai_ml_runtime.py     # RealAiMlRuntime: imports autoflow_ai in-process
└── mappers.py           # ML TaskGraph/outcome/events <-> CP Plan/status/events
```

Wire the `real` branches in `app/runtime.py` to `RealAiMlRuntime` (which calls
`AutoFlow.build().run_mission(...)` / `.dynamic_plan(...)`), gated by config:

```text
AUTOFLOW_INTELLIGENCE_MODE=mock|integration
AUTOFLOW_AI_ML_ENABLED=true
AUTOFLOW_AI_ML_TIMEOUT_SECONDS=...
# (in-process import; no AI_ML_URL needed for product path)
```

Because AI/ML is a Python package in the same repo, the adapter imports it
directly in the worker process (execution already runs off the request path via
the queue/worker). Failure isolation: wrap calls with timeouts + translate
`autoflow_ai` errors → CP `INTELLIGENCE_TIMEOUT`/`EXECUTION_FAILED` + events.

---

## 9. Integration granularity decision

AI/ML exposes two usable levels:

- **Level A (mission):** `AutoFlow.run_mission(prompt, target_path, use_model)`
  → returns a verified `MissionReport`. Simplest, real, already the CLI/flagship
  path. **Use this first.** CP maps: create plan from `dynamic_plan()`, then run
  the mission, translate its event bus → CP events, map `all_verified/outcome` →
  CP verification + terminal state; if the mission emits `approval.requested`,
  CP raises a real Approval and pauses.
- **Level B (per-step):** `dynamic_plan()` + drive `MultiAgentRuntime`/agents
  step-by-step so CP's execution controller runs the loop
  (agent→policy→approval gate→tool→verify) with full per-step events. More
  faithful to CP's controller; more adapter work. **Phase after Level A works.**

Start Level A (fastest honest end-to-end), evolve to Level B for per-step
approval/tool gating fidelity.

---

## 10. Risks

- **Enum case drift** everywhere → centralize in `intelligence/mappers.py`; add a
  contract test asserting every ML enum value maps to a CP value.
- **ML uses DEFAULT_ORG/WS** and no identity → CP must not trust ML for tenancy;
  CP passes its own execution context; ML identity is ignored on the wire.
- **ML tool execution does real side effects** (file writes, Word, browser,
  Needle) → integration mode must start with **safe tools only** (local file /
  artifact), real external actions (email/browser/Windows) stay opt-in + gated.
- **Long-running missions** run in a background thread inside AI/ML → CP worker
  must apply timeouts and not hold a request; execution already async via queue.
- **Approval authority** → ML may emit `approval.requested` but CP alone decides;
  ML must never proceed with a HIGH-risk send without CP-granted approval. In
  Level A the mission's `await_approval` path + CP approval must be reconciled
  (adapter pauses mission or splits the send into a CP-gated step).
- **Python version**: both backend and ai-ml target 3.11+/3.14; backend `.venv`
  is 3.14. AI/ML uses `uv`. Running AI/ML in-process from the backend venv means
  **backend venv must have `autoflow_ai` + its core deps installed** (editable
  install of `ai-ml`), or the worker runs in an env that has both.
- **Test baselines**: keep AI/ML (`~380`/`1068`) and backend (`35`) green; add
  integration tests separately; never weaken existing tests.

---

## 11. Exact implementation sequence

Small, testable phases. Mock mode stays the default throughout.

1. **Contract convergence** — `backend/app/intelligence/` package:
   `interfaces.py` (IntelligenceRuntime), `mappers.py` (enum + TaskGraph + event
   maps), `mock_runtime.py` (wraps existing mocks). Contract test: every ML enum
   value maps. *(No behavior change; mock still default.)*
2. **Real orchestrator (Level A planning)** — `RealAiMlRuntime.plan()` calls
   `AutoFlow.dynamic_plan()`; map `TaskGraph` → CP `Plan`; CP validates +
   persists. Test `test_real_orchestrator_integration`.
3. **Real agent/mission execution** — run the mission; translate events; map
   outcome. Test `test_real_agent_integration`.
4. **Real verification** — map `MissionReport.all_verified` + evidence → CP
   `VerificationResult`; CP gates COMPLETE. Test `test_real_verification_integration`.
5. **Full synthetic E2E** — `POST /tasks → real plan → real agent → safe tool →
   real verify → COMPLETE` via the worker + SSE. Test #4 from master prompt.
6. **Approval** — high-risk action → CP `AWAITING_APPROVAL` → approve →
   continue. Test #5.
7. **Safe real tools first**, then progressively enable documents/browser/desktop.
8. **Electron connected mode** — point `NEXT_PUBLIC_API_URL` at backend; verify
   the existing `backendRepository` + SSE render real data. No component rewrites.
9. **Chaos/reliability** — AI/ML unavailable, invalid plan, verification failure,
   recovery, approval expiry, reconnect replay, backend/worker restart, tenancy
   isolation, approval-hash invalidation, event honesty.

**First milestone (non-negotiable):**
`Electron → Control Plane → REAL orchestrator → REAL agent → safe tool → REAL
verification → Control Plane → SSE → Electron`, with nothing faked and no
existing tests weakened.

---

## 12. What will NOT change

- Desktop pages/components/design (only the data source flips via existing adapter).
- Backend API contracts, DB schema, state machine, approval/action-hash logic.
- AI/ML runtime internals (planner, agents, society, tools, verification, Needle).
- Mock mode (kept for dev/CI/offline/failure testing).
- The three-process boundary (Electron ≠ Control Plane ≠ AI/ML).
