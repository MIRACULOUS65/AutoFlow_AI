# AutoFlow AI — AI/ML Subsystem

**Purpose:** This directory is the intelligence and execution core of AutoFlow AI. It is built before the desktop client and must be usable, testable, observable, and stress-testable through Python APIs/CLI without Electron.

## 1. Mission

The AI/ML subsystem converts:

```text
ONE USER GOAL
     ↓
UNDERSTANDING
     ↓
AUTHORIZED CONTEXT
     ↓
PLAN
     ↓
SPECIALIST AGENT ASSIGNMENT
     ↓
MODEL ROUTING
     ↓
STRUCTURED ACTIONS
     ↓
DETERMINISTIC EXECUTION
     ↓
OBSERVATION
     ↓
VERIFICATION
     ↓
RECOVERY / REPLAN
     ↓
VERIFIED RESULT + ARTIFACTS
```

The subsystem must behave like an agentic work engine rather than a chat completion wrapper.

## 2. Scope of this folder

```text
ai-ml/
├── agents/                 # specialist agent implementations
├── computer_use/           # semantic browser/desktop intelligence
├── config/                 # AI/runtime configuration definitions
├── evals/                  # golden tasks, scenarios, benchmarks
├── model_gateway/          # provider/model abstraction and routing
├── models/                 # model manifests, adapters, prompt assets
├── orchestrator/           # plan execution and agent coordination
├── prompts/                # system prompts and prompt assembly
├── rag/                    # context retrieval interfaces
├── runtime/                # AI execution runtime and state handling
├── schemas/                # Pydantic/JSON-schema contracts
├── telemetry/              # AI-specific tracing and metrics
├── tests/                  # unit, integration, adversarial tests
└── docs/                   # AI/ML engineering documentation
```

## 3. Build rule

Do not begin by building the Electron UI. The AI/ML stack must first prove that an API request can complete a controlled end-to-end task.

```text
CONTRACTS
  → MODEL GATEWAY
  → PLANNER
  → AGENT RUNTIME
  → TOOL CALLING
  → EXECUTION RUNTIME
  → VERIFICATION
  → RECOVERY
  → RAG / MEMORY
  → STRESS HARNESS
  → BACKEND API
  → DESKTOP
```

## 4. Eight engineering documents

| Document | Purpose |
|---|---|
| `REQUIREMENTS.md` | Functional, non-functional and quality requirements |
| `TASKS.md` | Concrete implementation backlog and exit gates |
| `MODEL_AND_CONFIG.md` | Model strategy, provider adapters, environment, API keys and routing |
| `AGENT_BRAIN.md` | Planner, executor, specialist agents, memory and orchestration |
| `EXECUTION_RUNTIME.md` | Tool execution, state machine, computer use, verification and recovery |
| `PROMPTS_TOOLS_AND_SCHEMAS.md` | Prompt contracts, tool schemas, typed outputs and safety boundaries |
| `EVALUATION.md` | Stress testing, benchmarks, golden tasks, chaos and release gates |
| `README.md` | AI/ML folder map and operating rules |

## 5. Core rule

Models propose. Policies decide whether a proposed action is permitted. Deterministic runtimes perform side effects. Verifiers decide whether the intended outcome happened.

```text
MODEL
 ↓
TYPED PROPOSAL
 ↓
VALIDATION
 ↓
POLICY
 ↓
PERMISSION
 ↓
DETERMINISTIC TOOL
 ↓
OBSERVATION
 ↓
VERIFIER
```

No model receives unrestricted execution authority.
