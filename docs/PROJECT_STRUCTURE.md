# AutoFlow AI — Project Structure

**Purpose:** Define the repository as an executable architecture, not a loose collection of folders.

## 1. Root

```text
autoflow_ai/
├── docs/                    # System/product source of truth
├── ai-ml/                   # Brain: models, agents, planning, RAG, evals
├── backend/                 # Control plane: API, auth, orchestration, persistence
├── desktop/                 # Electron + React command center
├── infra/                   # Containers, cloud, staging, production manifests
├── scripts/                 # Developer and CI automation
├── examples/                # Golden tasks, sample data, demo environments
├── tests/                   # Cross-layer/end-to-end test suites
├── .env.example
├── .gitignore
├── README.md
└── LICENSE
```

## 2. Documentation Structure

```text
docs/
├── README.md
├── PRD.md
├── PROJECT_VISION.md
├── PROJECT_STRUCTURE.md
├── PROJECT_SETUP.md
├── SYSTEM_ARCHITECTURE.md
├── AI_ML_ARCHITECTURE.md
├── MULTI_AGENT_ARCHITECTURE.md
├── EXECUTION_ENGINE.md
├── API.md
├── AUTH_AND_TENANCY.md
├── KNOWLEDGE_AND_RAG.md
├── TOOL_CALLING.md
├── BROWSER_AUTOMATION.md
├── COMPUTER_USE.md
├── MODEL_ROUTING.md
├── WORKFLOW_ENGINE.md
├── APPROVALS.md
├── ARTIFACT_PIPELINE.md
├── AUDIT_AND_OBSERVABILITY.md
├── DESKTOP.md
├── DATABASE.md
├── EVALUATION.md
├── DEPLOYMENT.md
├── SECURITY.md
├── TASKS.md
└── DEMO_SCRIPT.md
```

Each document answers one engineering question. No implementation should depend on undocumented behavior.

## 3. AI/ML Tree

```text
ai-ml/
├── pyproject.toml
├── src/
│   └── autoflow_ai/
│       ├── agents/
│       │   ├── base.py
│       │   ├── planner.py
│       │   ├── execution.py
│       │   ├── research.py
│       │   ├── document.py
│       │   ├── spreadsheet.py
│       │   ├── presentation.py
│       │   ├── coding.py
│       │   ├── data_analysis.py
│       │   ├── communication.py
│       │   ├── computer_automation.py
│       │   └── verifier.py
│       ├── orchestrator/
│       ├── model_gateway/
│       ├── schemas/
│       ├── prompts/
│       ├── rag/
│       ├── tool_calling/
│       ├── computer_use/
│       └── recovery/
├── evals/
│   ├── golden_tasks/
│   ├── providers/
│   ├── computer_use/
│   ├── security/
│   └── reports/
└── tests/
    ├── unit/
    ├── agent/
    ├── workflow/
    └── integration/
```

The AI/ML package must be independently runnable by a CLI and test harness.

## 4. Backend Tree

```text
backend/
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── api/
│   ├── auth/
│   ├── tenancy/
│   ├── orchestration/
│   ├── executions/
│   ├── approvals/
│   ├── knowledge/
│   ├── artifacts/
│   ├── integrations/
│   ├── audit/
│   ├── workers/
│   ├── db/
│   ├── config/
│   └── observability/
└── tests/
```

The backend is authoritative for identity, workflow state, permissions and durable execution.

## 5. Desktop Tree

```text
desktop/
├── package.json
├── electron/
│   ├── main.ts
│   ├── preload.ts
│   └── ipc/
├── src/
│   ├── app/
│   ├── pages/
│   ├── components/
│   ├── features/
│   │   ├── auth/
│   │   ├── tasks/
│   │   ├── agents/
│   │   ├── workflows/
│   │   ├── knowledge/
│   │   ├── approvals/
│   │   ├── executions/
│   │   └── artifacts/
│   ├── state/
│   ├── api/
│   ├── types/
│   └── styles/
└── tests/
```

The desktop consumes backend APIs and event streams. It must not contain independent business logic.

## 6. Infrastructure

```text
infra/
├── docker/
├── compose/
├── migrations/
├── staging/
├── production/
├── monitoring/
└── secrets/
```

Infrastructure definitions must be reproducible and version controlled, while secret values themselves remain external.

## 7. Examples

```text
examples/
├── tasks/
│   ├── email_report.json
│   ├── browser_procurement.json
│   └── coding_patch.json
├── tools/
├── fixtures/
├── apps/
└── demo/
```

The examples folder becomes the source for repeatable golden tasks and demos.

## 8. Dependency Direction

```text
Desktop
   ↓
Backend API
   ↓
Execution / Orchestration
   ↓
AI/ML + Tool Runtime
   ↓
Providers / External Systems
```

Shared contracts should live in a dedicated versioned schema package to prevent circular dependencies.

## 9. Non-Negotiable Structure Rules

1. No provider secret in `desktop/`.
2. No core orchestration logic in React components.
3. No direct model calls scattered through agents; all go through Model Gateway.
4. No unrestricted side-effect function exposed directly to an LLM.
5. Every tool has a schema, permissions and verification contract.
6. Every material execution has persistent state.
7. Every new feature includes tests and documentation.

## 10. Build Order Reflected by the Repository

```text
contracts → ai-ml → backend → integrations → desktop → infra hardening
```

The folder structure itself should make the intended engineering order obvious.
