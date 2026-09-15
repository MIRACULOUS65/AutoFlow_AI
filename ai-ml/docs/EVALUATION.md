# AutoFlow AI — Evaluation

**Status:** growing with each phase. This document records how the AI/ML
subsystem is tested and how to reproduce results. No result is claimed here
unless it was actually executed.

## Test suite

```powershell
cd ai-ml
uv run pytest -q          # full suite
uv run pytest -m contract # contract tests only
uv run pytest -m unit
uv run pytest -m integration
uv run pytest --cov
```

Current status: **380 tests pass** (Phase 1–7 + Computer-Autonomy bundle),
including real live-desktop tests (Notepad via UI Automation) and a real headless
browser test (Chromium via Playwright on a controlled local page). Stress: 100
deterministic workflow runs + 30 failure-injection runs with **0 false-success**
(a workflow never reports SUCCESS unless the real side effect occurred).
Non-desktop/non-browser tests are hermetic — the model
gateway is forced to the local deterministic provider and RAG/memory use
temporary SQLite + Chroma directories, so no test hits the network or a paid
endpoint.

## Test pyramid (implemented so far)

| Level | Area | Files |
|---|---|---|
| Contract | schemas, DAG, tools, models, execution, approvals, workflows | `test_common`, `test_tasks_and_dag`, `test_tools`, `test_models`, `test_execution_and_approvals`, `test_workflows_and_events` |
| Unit | editing ops, context engine, token/budget/rank/sanitize, gateway config/policies/structured, embeddings | `test_editing`, `test_context_unit`, `test_model_gateway_*`, `test_rag_embeddings` |
| Integration | documents, tool runtime, HTTP+streaming providers, router/builder, RAG pipeline, memory, context/RAG/memory integration, end-to-end Golden 01 | `test_documents`, `test_runtime_tools`, `test_http_provider`, `test_streaming_provider`, `test_router_and_builder`, `test_rag_pipeline`, `test_rag_integration`, `test_memory`, `test_memory_integration`, `test_end_to_end` |

## Golden tasks

- **Golden 01** (document edit + save same file) — real `.docx` end to end.
- **RAG01–RAG16** — retrieval, isolation, provenance, poisoned-doc-as-data,
  versioning, failure handling.
- **M01–M20** — workflow memory: verified-only promotion, isolation, versioning,
  dedupe, compatibility, parameter binding, block/deprecate, provenance,
  security (secret/unregistered-tool rejection), and the reuse demo.
- **MA (multi-agent)** — dynamic planning + runtime: document workflow through
  agents, parallel research fan-in, bounded replan, unavailable/unregistered/
  unauthorized tool rejection, approval block, cycle + unknown-dep detection,
  malformed/unsupported agent handling, deadlock detection, and concurrency
  (20 parallel nodes, long chains). The real-model planner path is
  live-verified (fails closed to the deterministic planner).

- **DT (desktop tasks)** — computer use: launch/type/find/click/hotkey through
  the tool-calling controller + fake adapter; ambiguity, missing element, secret
  redaction, allowlist, approval gating. Two **real** desktop tests (Notepad
  launch/type/verify + desktop inspection) run live on Windows and **auto-skip**
  when no interactive desktop is available — never faked.

## Live provider + desktop verification

- NVIDIA `meta/llama-3.2-11b-vision-instruct` — chat, live-verified.
- ModelScope `Qwen/Qwen3-8B` — streaming reasoning model, live-verified.
- Embeddings: deterministic local embedder powers all tests/RAG/memory; a remote
  OpenAI-compatible embedder is available behind the same interface (unit-tested
  via transport; no live embedding endpoint on the current NVIDIA account).

## Metrics (recorded where measured)

CLI `autoflow model benchmark`, RAG/memory search latencies, and per-run traces
provide measured numbers. Reliability metrics (plan validity, verified
completion, recovery success, etc.) will be expanded with the Phase 17 stress
lab. Numbers are only reported when actually measured.


---

## True-Agentic + Integration milestone evaluation (2026-09-12)

Full suite: **626 passed, 6 skipped** (env-gated real integrations), compileall
clean. New evaluation assets:

- **True-agenticity acceptance** (`society/metrics.py::evaluate_agenticity`):
  scores 9 observable properties from the trace (supervisor present, delegation,
  ≥2-specialist handoff, state-dependent decision, observation→action,
  verification-gated execution, independent QA, tool-authority enforced,
  evidence-gated success). `is_true_agentic` requires the 7 core properties.
- **Stress**: 110 mixed missions (1/3 injected failures) + 25 delegation + 25
  disagreement + 25 flagship = **185+ mission executions, false_success = 0**.
- **Chaos/failure injection**: attachment failure, send failure, unconfirmed
  send, missing document, forced-reject critic, login-required, budget
  exhaustion — every one fails closed (no false success).
- **Security**: prompt/web/memory/blackboard injection stay DATA; unauthorized
  tool/permission blocked; secret redaction; approval tamper (recipient/body/
  attachment) invalidation; substituted approval rejected; path traversal
  rejected; forged verification not trusted.

### Live-verification status (honest)

- LIVE VERIFIED: web search + research (Bing/Chromium), vision (NVIDIA
  `meta/llama-3.2-11b-vision-instruct`), computer/Notepad (Windows UIA),
  real-model reasoning (NVIDIA/ModelScope).
- SKIPPED (env/credentials): real Gmail send (needs an authenticated controlled
  account + controlled recipient), real Word UI (`AUTOFLOW_REAL_WORD`).
- These are labeled SKIPPED/FUTURE, never reported as verified.
