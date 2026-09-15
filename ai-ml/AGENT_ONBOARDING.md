# AutoFlow AI/ML — Onboarding & Working Guide

The single starting point for anyone (human or AI agent) working in the `ai-ml/`
package. It tells you **what to read, what to skip, how to approach the code, how
to install everything (including Cactus Needle), and how to orchestrate missions
and Windows automation** without breaking the honesty guarantees.

---

## 0. The prime directives (read once, never violate)

1. **Never fake success.** A task is complete only when independent verification
   proves it. Model confidence ≠ verification. Tool success ≠ task success.
   Retrieval ≠ authorization.
2. **The model proposes; deterministic tools execute; verifiers confirm.** Never
   let a model output cause a side effect without schema validation + a real
   observation of the resulting state.
3. **Keep the test baseline green.** `1068 passed, 8 skipped` on Python 3.14 /
   Windows. Never weaken a test to make it pass; fix the real cause.
4. **Secrets never leave the boundary.** No keys in prompts, logs, traces,
   datasets, events, or Git. `.env` is gitignored.
5. **Honest labels only.** LIVE / INTEGRATION / SIMULATION / SKIPPED — say which
   one actually ran.

---

## 1. What to READ (in this order)

Start narrow and practical, go deeper only when the task needs it.

| Priority | Read | Why |
|---|---|---|
| 1 | **This file** | how to work here |
| 2 | Root `../README.md` | the whole product: models, agents, flow, frontend |
| 3 | `docs/INDEX.md` | the doc map + folder→doc mapping |
| 4 | `docs/MODEL_AND_CONFIG.md` | models, providers, env, key handling |
| 5 | `docs/AGENT_BRAIN.md` | agents, planner, executor, context, memory |
| 6 | `docs/EXECUTION_RUNTIME.md` | tools, computer use, verification, recovery |
| 7 | `docs/PROMPTS_TOOLS_AND_SCHEMAS.md` | typed model/tool contracts |

**Then read the code that your task actually touches** — use the folder map in
section 4. Read a module before you change it; never edit code you haven't read.

## 2. What to SKIP (unless your task is specifically about it)

- `../backend/docs/*` — backend is **docs-only**; the real local API lives in
  `ai-ml/src/autoflow_ai/server`. Don't build a separate backend.
- `../desktop/`, `../electron/` — placeholders; not part of the local product.
- `docs/TASKS.md`, `docs/REQUIREMENTS.md` — historical build order; useful for
  context, not for day-to-day changes.
- `docs/EVALUATION.md` — only when touching the eval/stress harness.
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, `uv.lock` — generated;
  never hand-edit (regenerate `uv.lock` via `uv` if deps change).
- `**/*.cact` weights — binary; don't open/edit. It's the bundled Needle model.

---

## 3. How to install everything

Prerequisites: **Python 3.11+ (3.14 verified)** and [`uv`](https://docs.astral.sh/uv/).

```powershell
cd ai-ml

# 1. Core (RAG, memory, docs, gateway, server) — always needed
uv sync

# 2. On-device Windows tool-calling model (Cactus Needle 2)
uv pip install cactus-needle
#    The fine-tuned weights (my_agent.cact ~14MB) already ship in the repo at
#    src/autoflow_ai/needle_agent/weights/, so nothing to download. First run
#    of the BASE model would fetch from HuggingFace; the bundled fine-tuned
#    weights avoid that.

# 3. Optional extras (install only what you need)
uv pip install ".[windows]"   # uiautomation — real Windows UIA desktop control
uv pip install ".[browser]"   # playwright — then: uv run playwright install chromium
uv pip install ".[vision]"    # opencv/numpy/pillow/mss — CV verification
uv pip install pywin32        # Word automation (win32com) for the Needle write_text tool

# 4. Configure cloud models (optional; offline works without this)
copy ..\.env.example ..\.env  # then set PRIMARY_MODEL_* (NVIDIA) / SECONDARY_MODEL_* (Qwen)

# 5. Verify the whole environment honestly
uv run python -m autoflow_ai.cli doctor
```

`doctor` reports PASS/WARN/FAIL/SKIPPED per subsystem (python, models, needle,
UIA, opencv, playwright, rag, memory, api, frontend). Anything you didn't install
shows **SKIPPED**, not FAIL.

---

## 4. How to approach the code (folder map)

Read the module that owns the behavior you're changing. Never guess an API.

| Folder | Owns | Read when |
|---|---|---|
| `orchestrator.py` | `AutoFlow` — the top-level facade wiring plan→run→verify | you touch mission execution |
| `planning/`, `brain/` | prompt → normalized task → `TaskGraph` (deterministic + model planners) | changing how plans are built |
| `agents/` | specialist agents (document, research, qa, browser, computer, …) | changing agent behavior |
| `society/` | supervisor, critic, grounding, simulation, flagship, research, websearch | changing orchestration/verification |
| `runtime/` | tool registry, tool-calling controller, document tools, multi-agent engine | changing execution/tool wiring |
| `model_gateway/` | provider abstraction, router, structured output, HTTP/local providers | changing model calls/routing |
| `editing/`, `documents/` | edit operations + `.txt/.md/.docx` adapters (real file I/O) | changing document editing |
| `computer_use/` | Windows UIA, browser (Playwright), CV/vision, autonomy loop | changing desktop/browser automation |
| `rag/`, `memory/`, `context/` | retrieval, workflow memory, context assembly + trust | changing grounding |
| `lab/` | Model Lab + manifest (benchmark/compare/install/verify) | changing model evaluation |
| `needle_agent/` | Cactus Needle 2 wrapper + 26 tools (`agent.py`, `tools.py`) | changing on-device automation |
| `server/` | stdlib HTTP API + SSE events + static frontend | changing API/UI |
| `schemas/` | typed contracts (plans, tools, enums) — the source of truth | almost always relevant |
| `tests/` | the behavior lock | before and after every change |

**Workflow for a change:** read the owning module + its schema → make the edit →
`uv run python -m compileall -q src` → run the focused test file → run the full
suite (`uv run pytest -q -k "not real_notepad and not real_word"`).

---

## 5. How to orchestrate a mission

A mission is: plan → supervisor delegates → specialists propose tool calls →
tools execute → observe real state → independent critic verifies.

```powershell
# Deterministic full loop (safe preview, no real side effects)
uv run python -m autoflow_ai.cli mission simulate --live

# Real mission against a real file (edits + saves it on disk, then verifies)
uv run python -m autoflow_ai.cli mission run `
  "replace the word DRAFT with FINAL and save the document" --file report.txt

# Same, model-driven planning instead of deterministic
uv run python -m autoflow_ai.cli mission run "...instruction..." --file report.txt --model
```

Programmatically:

```python
from autoflow_ai.orchestrator import AutoFlow

app = AutoFlow.build()
report, metrics, supervisor = app.run_mission(
    "replace the word DRAFT with FINAL and save the document",
    target_path="report.txt",
    use_model=False,        # True = use NVIDIA/Qwen for planning
)
assert report.all_verified   # False if the change did not actually land
```

Or over the API (what the frontend uses):

```
POST /missions            {"prompt": "...", "mode": "real", "target_path": "C:\\...\\report.txt"}
POST /missions/{id}/run   {"target_path": "C:\\...\\report.txt"}
GET  /missions/{id}/events   (SSE live stream)
GET  /missions/{id}          (status: complete ONLY when verified)
```

**Verification rule you must preserve:** for a replace/append instruction, the
mission verifier requires the requested text to actually be present in the
reopened file. If it isn't → `failed`, never `complete`.

---

## 6. How to do Windows automation

Two independent paths, both real, both opt-in.

### A. On-device Needle agent (fastest path to app-level actions)

The 45M Needle 2 model turns plain instructions into tool calls and runs them
on the CPU (no key, no cloud). Safe by default — add `--execute` for real actions.

```powershell
# plan only (no side effects) — see which tool the model picks
uv run python -m autoflow_ai.cli needle run "write hi my name is sam into notes.docx"

# actually perform it (creates a real file / opens a real app)
uv run python -m autoflow_ai.cli needle run "make a note that says buy milk" --execute
uv run python -m autoflow_ai.cli needle run "open youtube and play fifa theme song" --execute
```

Programmatic:

```python
from autoflow_ai.needle_agent import NeedleAgent

agent = NeedleAgent(execute=True, output_dir=r"C:\Users\me\Downloads")
result = agent.run("make a note that says buy milk")   # model picks + runs a tool
agent.close()
print(result.success, result.results)                  # real file written on disk
```

Notes:
- `execute=False` (default) returns the structured action WITHOUT touching the
  machine — use it in tests/preview.
- File writes are confined to `output_dir` (`AUTOFLOW_NEEDLE_OUTPUT` or
  `~/Downloads`). Word uses `win32com` when available, else falls back to a real
  `.txt` write.
- The model refuses ungrounded instructions ("ungrounded content") — that is the
  anti-hallucination guard working, not a bug. Phrase instructions concretely.

### B. Semantic UIA / browser control (through the agent society)

For missions that need real desktop/browser control inside the verified
orchestration loop, use the `computer_use` layer via the `computer`/`browser`
agents. These are opt-in and gated:

```powershell
uv pip install ".[windows]" ".[browser]"
uv run playwright install chromium
$env:AUTOFLOW_REAL_DESKTOP = "1"   # real UIA
$env:AUTOFLOW_ALLOW_WEB = "1"      # allowlisted real web
```

This path does semantic control (find element by role/label, observe, verify DOM/
window state) — not blind coordinate replay — and every action is verified.

---

## 7. Testing & release gate

```powershell
uv run python -m compileall -q src
uv run pytest -q -k "not real_notepad and not real_word"   # keep 1068 passed green
# live/opt-in tests (run only when you have the capability):
$env:AUTOFLOW_NEEDLE_LIVE = "1"; uv run pytest tests/test_needle_agent.py -q
```

If Notepad/Word windows were left open, close them first:
`Get-Process notepad, winword | Stop-Process -Force`.

---

## 8. Common pitfalls

- **Don't** call agent classes from the frontend — the UI speaks HTTP to the API
  only. Add a route, not a direct import.
- **Don't** add a heavy dependency to the core; use an optional extra in
  `pyproject.toml` and lazy-import it (like `needle_agent` does).
- **Don't** commit weights except the intentional Needle `.cact`. No `.gguf`,
  `.safetensors`, HF cache, or `.env`.
- **Don't** claim LIVE when you ran SIMULATION. Check the `mode`/`status` in the
  result before you report.
