# AutoFlow AI — AI/ML Core

The headless intelligence and execution core of AutoFlow AI. It runs and is
fully testable **without** the desktop client (Electron), through a Python API,
a CLI, and an automated test suite.

See `docs/` in this folder for the engineering specification. See
`../docs/IMPLEMENTATION_STATUS.md` for the current build phase.

## Requirements

- Python >= 3.11 (developed/verified on 3.14)
- [uv](https://docs.astral.sh/uv/) for environment + dependency management

## Setup (local)

```powershell
# from ai-ml/
uv venv
uv pip install -e ".[dev]"
```

## Run the CLI

The entire subsystem is drivable from the command line:

```powershell
# show versions
uv run autoflow version

# list every contract model
uv run autoflow contracts list

# build + JSON round-trip every contract (self-check)
uv run autoflow contracts check

# fast end-to-end contract smoke test (plan -> tool -> verify -> approval)
uv run autoflow eval smoke

# show the current implementation phase
uv run autoflow phase status
```

Each command exits non-zero on failure, so it can gate CI.

## Run the tests

```powershell
uv run pytest            # full suite
uv run pytest -m contract  # contract tests only
uv run pytest --cov        # with coverage
```

## Layout

```text
ai-ml/
├── pyproject.toml
├── src/autoflow_ai/
│   ├── schemas/         # Phase 1 — versioned Pydantic contracts
│   ├── samples.py       # canonical valid instances (fixtures + CLI self-check)
│   └── cli.py           # headless CLI entry point (`autoflow`)
├── tests/               # rigorous contract/unit tests
└── docs/                # AI/ML engineering documentation
```

## Phase status

- **Phase 1 (Contract layer):** implemented — ~33 versioned contracts, DAG
  validation, approval binding, tool-argument validation, execution state
  machine, secret-safe events.
- **Vertical slice (Golden 01):** real headless `.docx`/`.txt`/`.md` edit + save
  + verify via `autoflow run`.
- **Phase 2 (Model gateway):** provider-neutral gateway with real NVIDIA +
  ModelScope (SSE streaming) providers, retry/fallback/health, structured
  output; deterministic local fallback. CLI `autoflow model list|test|benchmark`.
- **Phase 3 (Context engine):** budgeted, trust-separated, ACL-filtered,
  deterministically-hashed context. CLI `autoflow context inspect|estimate|validate`.
- **Phase 4 (RAG):** persistent ChromaDB, docx/pdf/txt/md/json/csv ingestion,
  authorized semantic retrieval + evidence. CLI `autoflow knowledge ...`.
- **Phase 5 (Memory):** session + verified workflow memory (SQLite + separate
  `autoflow_workflows` collection) + graph memory; verification-gated promotion;
  semantic reuse with parameter binding. CLI `autoflow memory ...`.
- **Phase 6 (Dynamic Planner + Multi-Agent Runtime):** typed planner output +
  runtime task-graph + deterministic validator; specialist agent registry +
  `MultiAgentRuntime` (bounded concurrency, dependency resolution, bounded
  replanning). CLI `autoflow agents list|inspect`, `dynplan`, `run-agents`.
- **Phase 7 (Tool-Calling Controller + Windows Computer-Use):** `ComputerAdapter`
  + real `WindowsUIAutomationAdapter`; safe computer tools; `ToolCallingController`
  authority chain; real `ComputerAutomationAgent`. Live-verified with Notepad.
- **Computer-Autonomy bundle (Phases 8–14):** unified observation + fusion +
  target resolver; **real browser automation** (Playwright headless Chromium,
  local pages); vision interface + OpenCV deterministic CV; multi-signal
  verification engine; recovery ladder + stuck detection; approval binding +
  rate limits + resource locks; `AutonomyLoop`/`WorkflowExecution` observe→act→
  verify. Live-verified with a real browser form workflow. CLI
  `autoflow computer env|windows|inspect`.
  (Install extras: `uv pip install -e ".[dev,windows,vision,browser]"`, then
  `uv run playwright install chromium`.)

See `../docs/IMPLEMENTATION_STATUS.md` for the authoritative ledger. All phases
verified by the test suite (380 tests, incl. real desktop + real browser) and
the CLI.
