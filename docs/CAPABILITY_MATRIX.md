# AutoFlow AI — Capability Matrix

Honest status of every capability. Labels:

- **LIVE** — runs against the real thing right now (verified on this machine).
- **INTEGRATION** — real code path wired end-to-end; goes LIVE when the env
  flag / credential / hardware is present; otherwise reports honestly.
- **SIMULATION** — the full real loop over a deterministic environment (no real
  cloud/desktop side effect). This is the default safe mode.
- **SKIPPED** — gated off by default; enabled only via explicit opt-in flag.

Verified via `autoflow doctor`: **14 PASS, 1 SKIPPED, 0 FAIL** on the reference
machine (Python 3.14, Windows). The one SKIPPED is web access (opt-in).

| Capability | Status | Simulation available | Gate / how to enable | Notes |
|---|---|---|---|---|
| Agentic runtime (plan → delegate → verify) | LIVE | Yes | always on | Supervisor + specialists + independent critic |
| Local orchestration API (`autoflow serve`) | LIVE | — | always on | stdlib http.server, localhost, no extra deps |
| Frontend (single page + SSE events) | LIVE | — | always on | served at `/`; shows COMPLETED only from real backend status |
| Real-time event stream (SSE) | LIVE | Yes | always on | canonical event contract, secret-redacted |
| Local deterministic model (`local-rule`) | LIVE | — | always on | offline reproducible baseline |
| NVIDIA model (primary) | INTEGRATION | Yes | `PRIMARY_MODEL_*` in `.env` | LIVE-verified; fails closed on timeout |
| Qwen / ModelScope model (secondary) | INTEGRATION | Yes | `SECONDARY_MODEL_*` (+`_STREAMING`) | streaming LIVE-verified |
| Embeddings (semantic RAG) | INTEGRATION | Yes (local hash) | `EMBEDDING_*` | local deterministic embeddings without config |
| Model Lab (benchmark/compare/score) | LIVE | Yes | always on | structural + hallucination + malformed-output labs |
| RAG knowledge retrieval | LIVE | — | always on | KnowledgeService buildable (doctor PASS) |
| Workflow / session memory | LIVE | — | always on | MemoryService buildable (doctor PASS) |
| EvidenceBroker grounding | LIVE | Yes | always on | trust + provenance merge; retrieval ≠ authorization |
| Web research (real browser + DOM) | INTEGRATION | Yes | `AUTOFLOW_ALLOW_WEB=1` | allowlisted search hosts; reports NONE honestly |
| Browser control (Playwright/Chromium) | INTEGRATION | Yes | Chromium installed + opt-in | doctor: installed |
| Desktop control (Windows UIA) | INTEGRATION | Yes | interactive desktop | semantic control, not coordinate replay |
| Vision / OpenCV verification | INTEGRATION | Yes | OpenCV present (doctor PASS) | multi-signal verification |
| Real Word document UI | SKIPPED | Yes | `AUTOFLOW_REAL_WORD=1` | otherwise document ops simulated |
| Real Gmail send | SKIPPED | Yes | `AUTOFLOW_REAL_GMAIL=1` + controlled account | approval-bound side effect |
| Live NVIDIA benchmark runs | SKIPPED | Yes | `AUTOFLOW_LIVE_NVIDIA=1` | otherwise structural/simulated |
| Mission checkpoint / resume | LIVE | Yes | `--persist` / `--resume` | store at `AUTOFLOW_MISSION_DIR` |
| On-device tool-calling agent (Needle 2) | LIVE | Yes (plan-only) | `uv pip install cactus-needle` | 45M-param model, ~14MB fine-tuned weights bundled; runs on CPU, no cloud/key; `--execute` for real actions |

## Modes in practice

- **Out of the box (no config):** everything runs in **SIMULATION** over the
  local deterministic provider — the real agentic loop, real event stream, real
  verification, no cloud/desktop side effects. The `demo` command exercises this
  path end-to-end.
- **With models configured:** planning/execution use the real NVIDIA/Qwen models
  (**INTEGRATION → LIVE**).
- **With opt-in flags:** real web, real Word, real Gmail, live NVIDIA benchmarks
  go **LIVE**. Each is off by default and fails honestly if unavailable.

## Verification commands

```powershell
cd ai-ml
uv run python -m autoflow_ai.cli doctor        # PASS/WARN/FAIL/SKIPPED per subsystem
uv run python -m autoflow_ai.cli demo          # deterministic flagship, complete:true
uv run python -m autoflow_ai.cli serve         # then open http://127.0.0.1:8770
```
