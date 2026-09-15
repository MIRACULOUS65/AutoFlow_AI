# AutoFlow AI — AI/ML Implementation Tasks and Exit Gates

**Status:** living backlog for the AI/ML subsystem
**Convention:** phases here mirror the master implementation phase plan
(Phase 0 = repo audit; Phase 1 = contracts; …). Each phase must be runnable
and tested from the CLI before the next begins.

---

## Phase 1 — Contract layer ✅ (implemented)

- [x] Scaffold `ai-ml/` package with `uv` (`pyproject.toml`, `src/` layout,
      `tests/`, pytest config).
- [x] Enums (`schemas/enums.py`): risk, model role/modality/deployment/health,
      agent kind, action type, execution/step status, verification, recovery,
      approval, memory, trust, artifact, trigger, event, actor.
- [x] Common base (`schemas/common.py`): `AutoFlowModel` (extra=forbid,
      validate_assignment), `VersionedModel`, deterministic `to_json` /
      `canonical_dict` / `compute_hash`, ID validation, `Tenancy`,
      `Principal`, `Reference`, `Timestamped`.
- [x] ~33 versioned contracts across models, tools, tasks/planning, agents,
      knowledge/context/memory, execution/observation/verification/recovery,
      approvals, workflows/artifacts/automation, events/audit.
- [x] DAG validation (no cycles, valid refs, unique ids, no dup edges,
      topological order).
- [x] Approval binding to exact plan version + action hash.
- [x] Tool argument validation against a JSON-Schema subset.
- [x] Execution state-machine transition table.
- [x] Secret-leak guard on event payloads.
- [x] Headless CLI: `version`, `contracts list`, `contracts check`,
      `phase status`, `eval smoke`.
- [x] Rigorous test suite (95 tests, 97% coverage) + CLI self-checks.

**Exit gate (met):** invalid plans/tools/workflows/approvals are rejected;
all contracts serialize/deserialize deterministically; `autoflow contracts
check` and `autoflow eval smoke` pass; `uv run pytest` is green.

---

## Vertical Slice — Golden 01 (edit a document, save same file) ✅ (implemented)

A real, runnable, headless end-to-end pipeline proving the architecture, built
across all layers rather than one horizontal layer at a time. No mocks, no
network, no backend, no Electron.

- [x] **Model gateway** — `ModelProvider` protocol; deterministic offline
      `LocalRuleProvider`; `ModelRegistry`; `ModelRouter` with capability
      selection + bounded fallback. (`model_gateway/`)
- [x] **Intent normalizer** — prompt → `NormalizedTask` (detects edit ops,
      resolves target file). (`brain/normalizer.py`)
- [x] **Planner** — `NormalizedTask` → validated `TaskGraph`
      (inspect→edit→save→verify DAG). (`brain/planner.py`)
- [x] **Edit operations** — structured, deterministic transforms
      (replace, em-dash normalize, double-space, space-before-punct, trim).
      (`editing/operations.py`)
- [x] **Document adapters** — real `.docx` (python-docx, run-by-run, structure
      preserving), `.txt`, `.md`. (`documents/`)
- [x] **Tool registry + document tools** — `document.inspect/edit/save`,
      registry-bound, schema-validated, permissioned. (`runtime/registry.py`,
      `runtime/document_tools.py`)
- [x] **Execution engine** — DAG walk; agent proposes action → validate →
      permission check → tool → observation → verification → bounded recovery;
      emits trace + events; never COMPLETE without verification.
      (`runtime/engine.py`)
- [x] **CLI** — `autoflow run|inspect|plan|validate` with readable trace.
- [x] **Tests** — 138 passing (unit + integration + real e2e on a `.docx`
      fixture), 94% coverage; golden acceptance test asserts actual saved
      content.

**Verify:**

```powershell
uv run autoflow run "Edit this Word file, fix the wording, normalize em-dashes, remove double spaces, and save the edited version to the same file." --file tests/fixtures/sample.docx
uv run pytest -q
```

**Deliberately deferred (per plan):** Gmail/email, real browser automation,
global keyboard/mouse control, ChromaDB/RAG, Electron, backend, cloud deploy.

---

## Phase 2 — Real model gateway ✅ (implemented)

- [x] `ModelProvider` protocol; deterministic local provider retained for tests.
- [x] Real provider adapter: `OpenAICompatibleProvider` (OpenAI/vLLM/LM Studio/
      Ollama-compatible) over stdlib urllib — imports without network, pluggable
      transport for tests. (`model_gateway/http_provider.py`)
- [x] Env-based config loader with a minimal `.env` reader; secret-safe
      (`api_key` repr-excluded, `redacted()` masks it, never logged/in prompts).
      (`model_gateway/config.py`)
- [x] Policies: `RetryPolicy` (per-provider bounded retry + backoff),
      `FallbackPolicy` (bounded cross-model fallback), `ProviderHealth` (rolling
      health de-prioritizes flappers). (`model_gateway/policies.py`)
- [x] `StructuredOutputParser` — extracts JSON from prose/fenced/braced text and
      validates into a Pydantic model; raises on garbage.
      (`model_gateway/structured.py`)
- [x] Router upgraded: capability selection + retry + bounded fallback + health;
      auth errors are non-retryable. (`model_gateway/router.py`)
- [x] `build_gateway()` assembles registry+router from config; real provider
      first, local provider always kept as offline fallback.
      (`model_gateway/builder.py`)
- [x] Model test/benchmark harness on AutoFlow-shaped tasks (not chat trivia).
      (`model_gateway/harness.py`)
- [x] CLI: `autoflow model list|test|benchmark`.
- [x] Tests: config, policies, structured parser, HTTP adapter (real in-process
      localhost server + injected-transport failure modes), router
      retry/fallback/health, builder, harness. **176 tests pass** (138 prior +
      38 new), zero regressions.

**Exit gate (met):** model selectable by capability; provider failure →
controlled fallback; timeout/auth/malformed/500 mapped to controlled errors;
structured output validated; credentials never hardcoded, logged, or placed in
prompts. Orchestrator now uses the built gateway (real provider when configured,
local otherwise) with no change to the execution engine.

**Phase 2 addendum — streaming (implemented):** the OpenAI-compatible provider
now supports SSE streaming, aggregating deltas into a normalized ModelResponse
and **discarding `reasoning_content`** (no chain-of-thought leaves the gateway).
Models set `requires_streaming=True` (schema flag) when a provider only returns
content via streaming. ModelScope (Qwen/Qwen3-8B) is wired as a SECONDARY
provider and **live-verified** through the gateway. 9 streaming tests added
(fake SSE transport + reasoning-dropped + structured + failure modes). Total 253
tests pass.

**Still open for Phase 2 hardening (deferred):** async transport + real backoff,
per-role model selection (distinct planner/executor/vision models), token-level
streaming to callers (we aggregate internally).

---

## Phase 3 — Context engine ✅ (implemented)

- [x] Trust model: 8 ordered trust classes; only SYSTEM/user/app-state may act
      as instructions; retrieved/tool/external content is always DATA.
      (`context/trust.py`)
- [x] `ContextItem` + 14 canonical sections with provenance, permission scope,
      trust, importance/relevance/freshness, token estimate, content hash.
      (`context/items.py`)
- [x] `TokenEstimator` (deterministic approximation, explicitly an estimate,
      replaceable). (`context/tokens.py`)
- [x] `ContextBudgetPolicy` — reserves output tokens FIRST, then allocates the
      input budget per-section by weight; no hardcoded window. (`context/budget.py`)
- [x] `ContextRanker` — deterministic multi-factor (relevance/importance/trust/
      freshness/provenance), ties broken by id. (`context/ranker.py`)
- [x] `ContextSanitizer` — quarantines malformed provenance / trust-source
      mismatch WITHOUT rewriting source meaning. (`context/sanitizer.py`)
- [x] `AuthorizationFilter` — excludes cross-tenant/workspace/permission content
      BEFORE assembly (authorization is not the model's job). (`context/authorization.py`)
- [x] `ContextAssembler` — authorize → sanitize → dedupe → estimate → rank →
      budget → sectioned bundle. (`context/assembler.py`)
- [x] `ContextBundle` — manifest, deterministic `context_hash()`, dropped-item
      + compression records, `render_prompt()` that wraps untrusted content as
      `<data>` so it can never be an instruction. (`context/bundle.py`)
- [x] Wired into the orchestrator between normalizer and the model call; the
      execution engine and Golden 01 are unchanged.
- [x] CLI: `autoflow context inspect|estimate|validate` (secret-safe, `--redact`).
- [x] Tests: unit (items/estimator/budget/ranker/authorization/sanitizer/
      assembler/hash) + 8 adversarial scenarios + orchestrator integration.
      **208 tests pass** (176 prior + 32 new); Golden 01 still green.

**Exit gate (met):** trust enforced; authorization seam before assembly;
provenance preserved; deterministic hashing; output reserve; oversized context
bounded; duplicates removed; injected instructions stay data; observation
freshness respected; approval state authoritative; CLI works; no secrets leak.

**Deferred (not this phase):** semantic relevance scores (Phase 4 RAG plugs into
`ContextItem.relevance`), real tokenizer, context compaction/summarization of
long histories.

## Phase 4 — ChromaDB + knowledge (RAG) ✅ (implemented)

- [x] `rag/` package: models, config, errors, loaders, chunking, embeddings,
      chroma_store, filters, ranking, retriever, service.
- [x] Real persistent ChromaDB (custom embeddings — no onnxruntime dep);
      physical `where` metadata filtering = authorization (similarity ≠ permission).
- [x] Loaders: docx/pdf/txt/md/json/csv with page/section metadata; path
      security + size/chunk limits; safe failure on malformed/empty/unsupported.
- [x] Deterministic chunker (size/overlap, content-hashed chunks).
- [x] `EmbeddingProvider` interface with **two real** implementations:
      `LocalHashingEmbedder` (deterministic, offline, honest baseline) and
      `RemoteEmbedder` (OpenAI-compatible /embeddings: NVIDIA/ModelScope/OpenAI).
      Embedder signature guards against mixing models in one collection.
- [x] `Retriever`: authorize → search → python-side permission check → score
      normalization → dedupe → rerank interface → evidence; distinguishes
      NO_RESULTS vs NO_AUTHORIZED_EVIDENCE (RetrievalStatus model).
- [x] `KnowledgeService`: ingest/search/get/delete/reindex/health with content-
      hash idempotency + versioning; embedding failure aborts (never partial/fake).
- [x] Integrated into the context engine: retrieved knowledge enters as
      AUTHORIZED_KNOWLEDGE **data** (wrapped `<data>`, never instructions);
      retrieval is optional and skipped when no KnowledgeService is attached
      (Golden 01 unaffected).
- [x] CLI: `autoflow knowledge ingest|search|inspect|delete|health` (secret-safe).
- [x] Synthetic dataset `examples/knowledge/*.md` (sales/finance/eng/hr/email/
      handbook) with overlapping wording + workspace scopes.
- [x] Tests: 16 golden RAG scenarios + tenant/workspace isolation + permission
      denial + poisoned-doc-stays-data + versioning + idempotency + embedding
      determinism + failure handling + path security + full pipeline +
      context-RAG integration. **244 tests pass** (208 prior + 36 new), real
      local ChromaDB + real embedder, temp-isolated.

**Exit gate (met):** authorization is physical (not similarity); tenant/workspace
isolation verified; provenance/evidence preserved and never fabricated; injected
document instructions remain data; NO_AUTHORIZED_EVIDENCE distinct from
NO_RESULTS; embedding/store failures are controlled; Golden 01 still green.

**Live-verification note:** NVIDIA chat inference is live-verified. NVIDIA
*embedding* models 404 for this free-tier account's deployment, so remote
embeddings are verified via the adapter's transport interface (unit-tested), not
a live call; the local deterministic embedder powers the live RAG demos.
Deferred: real remote embedding live call (needs an account with an embedding
model deployed), cross-encoder/LLM reranker, semantic chunking.

## Phase 5 — Memory ✅ (implemented)

- [x] Four distinct memory classes (never collapsed): SESSION (bounded,
      serializable), KNOWLEDGE (Phase 4 RAG, unchanged), WORKFLOW (verified
      reusable semantic workflows), GRAPH (apps/tools/actions/artifacts/wf).
- [x] `memory/` package: models, config, errors, storage (SQLite + dedicated
      `autoflow_workflows` Chroma collection reusing the RAG embedder),
      session, normalization, scoring, compatibility, promotion, graph, service.
- [x] Trace normalization → SemanticWorkflow (strips coordinates/DOM noise;
      extracts `${param}` parameters; routes `.verify` to verification rules).
      Step names are semantic (a validator rejects coordinate-like names).
- [x] Verification-gated promotion: failed/cancelled/unverified never promoted;
      secret scan; unregistered tools rejected; configurable human confirmation.
- [x] Immutable versioning + content-hash dedupe (identical → reuse; different
      → new version).
- [x] Authorized semantic retrieval (tenant/workspace physical filter + scope
      check); blocked never returned; deprecated deprioritized; explainable
      multi-signal score (semantic + compatibility + verified-success + recency,
      failure decay).
- [x] Compatibility check (COMPATIBLE / PARTIALLY / INCOMPATIBLE) + parameter
      binding that preserves semantics.
- [x] Graph memory (USES/PRODUCES/VERIFIED_BY relationships).
- [x] Integrated into the context engine (WORKFLOW_MEMORY as AUTHORIZED_MEMORY
      **data**, wrapped `<data>`) and orchestrator (`learn_from_run` creates +
      promotes a candidate from a verified run; retrieval optional, Golden 01
      unaffected).
- [x] CLI: `autoflow memory status|workflows|search|inspect|versions|deprecate|
      block|graph` (explicit ids only; no fuzzy promotion).
- [x] Tests: 20 M-tasks + RAG/memory separation + graph + security
      (secret/unregistered-tool rejection) + session bounds + versioning/dedupe
      + compatibility + parameter binding + **live reuse demo** (learn from a
      real document run, then retrieve semantically). **283 tests pass**
      (253 prior + 30 new); temp SQLite+Chroma isolation; Golden 01 + RAG green.

**Exit gate (met):** verified-only promotion; workflow memory physically
separate from knowledge RAG; tenant/workspace isolation; blocked non-executable;
provenance preserved; secrets not persisted; deterministic hashing/dedupe;
context + reuse integration works; no fake claims (this is workflow learning,
not model-weight training).

**Deferred:** cross-encoder reranking for workflows, richer graph queries,
human-in-the-loop promotion UI (policy hook exists), persistent session store.

## Phase 6 — Dynamic Planner + Multi-Agent Runtime ✅ (implemented)

- [x] `planning/` package: typed `PlannerOutput`, `RuntimeGraph` + `PlanNode`
      node state machine, deterministic `validate_plan` (cycles, unknown/self
      deps, dup ids, unknown agents, unregistered tools, unavailable caps,
      ungranted perms, high-risk approval/verification gates).
- [x] `DeterministicPlanner` (rule-based → always-valid graph) + `ModelPlanner`
      (structured output via gateway; **fails closed** to deterministic).
- [x] `agents/` package: `SpecialistAgent` base, explicit `AgentContext`,
      structured `AgentResult`/`AgentActionProposal`, `AgentRegistry`, nine
      specialists (document/research/spreadsheet/qa/presentation/coding/
      communication executable; **browser/computer real interfaces returning
      UNSUPPORTED**, never faked).
- [x] `runtime/multi_agent.py`: `MultiAgentRuntime` scheduler — ready-node
      selection, bounded `ThreadPoolExecutor` concurrency, dependency fan-out/
      fan-in, deadlock detection, per-tool lock; authority chain preserved
      (propose → validate → policy → permission → approval → ToolRegistry →
      observe → verify); bounded replanning; serializable secret-free events.
- [x] Orchestrator `dynamic_plan` + `run_multi_agent` (opt-in; single-agent
      `run()`/Golden 01 untouched); verified runs feed Phase 5 promotion.
- [x] CLI: `agents list|inspect`, `dynplan`, `run-agents [--model]`.
- [x] MA golden + adversarial + deadlock + concurrency tests (41 new; 324 total).
      Real-model planner path live-verified.

**Not implemented (honest):** browser automation (separate future phase), agent
output streaming.

## Phase 7 — Tool-Calling Controller + Windows Computer-Use ✅ (implemented)

- [x] `computer_use/` package: `ComputerAdapter` interface; real
      `WindowsUIAutomationAdapter` (uiautomation/UIA — semantic role/name/aid
      resolution, ambiguity detection, allowlisted launch, no coordinate-primary
      interaction); deterministic `FakeDesktopAdapter`; semantic models
      (`UIElement`/`WindowInfo`/`DesktopObservation`/`ActionResult`) + semantic
      `desktop_state_hash`; risk classes; guarded import.
- [x] Safe computer tools registered into the **existing** `ToolRegistry`
      (inspect/list_windows/focus/find/launch/click/type/press_key/hotkey/
      wait_for); destructive/shell tools **never registered**; app launch
      allowlisted at the tool layer.
- [x] `runtime/tool_calling.py` `ToolCallingController`: proposal → schema →
      registry lookup → authorization → policy/risk → approval → execute →
      sanitized trace (secrets/typed-text redacted).
- [x] `ComputerAutomationAgent` upgraded to real (proposes one semantic action
      per node; NOOP/UNSUPPORTED only when honestly so); runs inside the
      existing `MultiAgentRuntime`; deterministic planner recognizes Notepad
      tasks. CLI `autoflow computer env|windows|inspect`.
- [x] Tests: hermetic tool-calling/UI-discovery/ambiguity/state-hash/safety/
      redaction + adversarial (blocked/unknown/unauthorized/arbitrary-exe/secret/
      malformed) + DT golden tasks + **2 real live-desktop tests** (Notepad
      launch/type/verify + desktop inspection) that actually executed. 28 new;
      **352 tests pass**.

**Live-verified** on Windows (UIA adapter, real Notepad workflow, semantic state
change confirmed).

**Not implemented (honest):** browser automation (separate phase), screenshot/
vision grounding (interface present, capture deferred), Word automation
(interface supports it; not exercised in CI).

## Phase 7 (AI/ML numbering) — Request normalizer

- [ ] `IntentNormalizer` → `NormalizedTask`.

## Phase 7 — Planner

- [ ] Planner agent → `TaskGraph`; deterministic plan validation.

## Phase 8 — Agent system

- [ ] Shared agent runtime; specialist profiles; dynamic assignment.

## Phase 9 — Execution agent

- [ ] State-driven next-action proposal within policy.

## Phase 10 — Tool calling

- [ ] `ToolRegistry`, `ToolSchemaValidator`, `ToolSelector`,
      `ArgumentValidator`, `ConfidenceGate`, `ToolPermissionResolver`.

## Phase 11 — Deterministic tool runtime

- [ ] Files/documents/browser/desktop/code/communication/knowledge tools
      behind deterministic adapters with observation + verification.

## Phase 12 — Computer/browser abstraction

- [ ] Semantic targets, resolution hierarchy, visual grounding fallback.

## Phases 13–19

- [ ] Document workflow E2E; email approval workflow E2E; approval engine;
      verification; recovery/replanning; semantic workflow generation;
      automation engine.

## Phases 20–24

- [ ] Backend integration; databases; event system; test environments;
      evaluation/stress harness (golden + adversarial + chaos).

---

## Standing rules for every phase

1. Models propose; deterministic runtime executes; verifiers confirm.
2. No tool outside the registry; deny-by-default permissions.
3. Every material step verified; tool success ≠ business success.
4. Approval binds to exact plan/action version.
5. Bounded autonomy — no infinite loops.
6. Runs headlessly from the CLI; every behavior has tests.
7. Never fake an integration; never report unexecuted tests as passing.


## Computer-Autonomy Bundle (Phases 8–14) ✅ (implemented)

All in `computer_use/` (+ `runtime/tool_calling.py`), composing on Phase 1–7.

- [x] Unified observation + `ObservationFusion` + `TargetResolver` (RESOLVED/
      AMBIGUOUS/NOT_FOUND/DISABLED/HIDDEN/STALE) — never guesses.
- [x] Browser: `BrowserAdapter` + `FakeBrowserAdapter` + real
      `PlaywrightBrowserAdapter` (headless Chromium, local pages only, remote
      nav blocked); safe browser tools in the existing registry. **LIVE VERIFIED.**
- [x] Vision: provider-neutral `VisionProvider` + `FakeVisionProvider` +
      `RateLimitedVision` (per-task/minute budget, duplicate-screenshot
      suppression). Live vision-model call is FUTURE (interface done).
- [x] Deterministic CV (OpenCV 5): perceptual hash, image diff, stability,
      template match; graceful degrade if opencv absent.
- [x] `VerificationEngine` — multi-signal (UI/DOM/file/document/app-state/text);
      action-executed never equals success.
- [x] `RecoveryEngine` (bounded ladder) + `StuckDetector` (repeated state/action)
      preserving completed work.
- [x] Approval binding (`ApprovalLedger`/`ApprovalRequest` — bound to exact
      action+args+observation hash, invalidated on material change), `RateLimits`,
      `ResourceLocks`.
- [x] `WorkflowExecution` + `AutonomyLoop` (observe→act→verify→recover;
      serializable trace). **LIVE VERIFIED** with browser.
- [x] Tests: 28 autonomy + stress (100 deterministic runs, **0 false-success**;
      30 failure-injection, 0 false-success) + real browser + real Notepad
      (Phase 7). **380 tests pass.**

**Live-verified:** real headless Chromium form workflow; real Notepad desktop
workflow (Phase 7). **Not implemented (honest):** live vision-model grounding
call, Word E2E via UIA in CI, GUI screenshot capture wired into the loop.
