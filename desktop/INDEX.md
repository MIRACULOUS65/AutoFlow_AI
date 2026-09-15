# AutoFlow AI — AI/ML Documentation Index

## Read in this order

1. `README.md` — scope and architecture rules
2. `REQUIREMENTS.md` — what must exist
3. `TASKS.md` — what to build and in what order
4. `MODEL_AND_CONFIG.md` — models, providers, environment and API-key handling
5. `AGENT_BRAIN.md` — agents, planner, executor, context and memory
6. `EXECUTION_RUNTIME.md` — tools, computer use, verification and recovery
7. `PROMPTS_TOOLS_AND_SCHEMAS.md` — typed model/tool contracts
8. `EVALUATION.md` — stress testing and release gates

## Folder-to-document mapping

| Folder | Primary document |
|---|---|
| `model_gateway/` | `MODEL_AND_CONFIG.md` |
| `agents/` | `AGENT_BRAIN.md` |
| `orchestrator/` | `AGENT_BRAIN.md`, `EXECUTION_RUNTIME.md` |
| `tool_calling/` | `PROMPTS_TOOLS_AND_SCHEMAS.md`, `EXECUTION_RUNTIME.md` |
| `computer_use/` | `EXECUTION_RUNTIME.md` |
| `schemas/` | `PROMPTS_TOOLS_AND_SCHEMAS.md` |
| `rag/` | `AGENT_BRAIN.md` |
| `evals/` | `EVALUATION.md` |
| `tests/` | `REQUIREMENTS.md`, `EVALUATION.md` |
