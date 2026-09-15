# AutoFlow AI — Model, Provider and Configuration Architecture

## 1. Principle

AutoFlow AI is model-agnostic. The application asks for capabilities and policies; the Model Gateway decides which eligible model/provider should handle the request.

```text
AGENT NEED
  ↓
CAPABILITY REQUEST
  ↓
MODEL REGISTRY
  ↓
POLICY FILTER
  ↓
HEALTH / LATENCY / COST FILTER
  ↓
ROUTER
  ↓
PROVIDER ADAPTER
  ↓
MODEL API
```

## 2. Model roles

Do not force one model to perform every job.

| Role | Responsibility |
|---|---|
| Planner model | understand goal and build structured plan |
| Reasoning/execution model | choose next safe action from current state |
| Tool-calling model | map semantic operation to a narrow function call |
| Vision model | screen/document understanding and grounding |
| Coding model | repository/code reasoning and test repair |
| Embedding model | semantic retrieval |
| Reranker | optional retrieval refinement |

A single model may serve multiple roles when evaluation proves it is suitable.

## 3. Provider abstraction

Every provider adapter implements one contract conceptually equivalent to:

```python
class ModelProvider:
    async def generate(self, request): ...
    async def stream(self, request): ...
    async def embed(self, request): ...
    async def health(self): ...
```

Adapters belong in `model_gateway/providers/`.

## 4. Model manifest

Each model should be described by machine-readable metadata.

```yaml
id: provider/model-id
provider: provider-name
display_name: Example Model
roles:
  - planner
  - executor
capabilities:
  text: true
  vision: false
  tool_calling: true
  structured_output: true
  coding: true
context_window: 128000
policy_tags:
  - approved-dev
limits:
  max_tokens: 8192
routing:
  priority: 100
  expected_latency_ms: 2500
```

## 5. Routing policy

Routing must consider:

1. capability compatibility;
2. required modality;
3. structured-output guarantees;
4. tool-calling support;
5. context size;
6. task risk;
7. workspace policy;
8. provider health;
9. latency budget;
10. cost budget;
11. recent evaluation quality.

## 6. Configuration hierarchy

Recommended precedence:

```text
DEFAULT CONFIG
    ↓
ENVIRONMENT CONFIG
    ↓
WORKSPACE CONFIG
    ↓
TASK-SCOPED POLICY
```

Secrets must be resolved only at the provider/connector boundary.

## 7. Environment variables

Use `.env.example` as documentation only. Real secrets live outside source control.

Example categories:

```text
APP_ENV=development
LOG_LEVEL=INFO

PRIMARY_MODEL_PROVIDER=...
PRIMARY_MODEL_ID=...
PRIMARY_MODEL_API_KEY=...

SECONDARY_MODEL_PROVIDER=...
SECONDARY_MODEL_ID=...
SECONDARY_MODEL_API_KEY=...

EMBEDDING_PROVIDER=...
EMBEDDING_MODEL_ID=...
EMBEDDING_API_KEY=...

RAG_ENDPOINT=...
RAG_API_KEY=...

BROWSER_EXECUTION_ENABLED=true
DESKTOP_EXECUTION_ENABLED=false

MAX_MODEL_CALLS_PER_TASK=...
MAX_EXECUTION_SECONDS=...
MAX_REPLANS=...
```

Do not commit real values.

## 8. API-key handling requirements

- keys are backend-side only;
- never send provider keys to the Electron renderer;
- never place keys in prompts;
- redact Authorization headers from logs;
- rotate keys without code changes;
- use separate credentials for local development, CI and production;
- support secret-manager integration in production;
- expose only provider health/configuration metadata to clients.

## 9. Hosted/API-first operation

The initial product uses provider APIs as the default intelligence path. Local/self-hosted models are optional adapters and must obey the same contracts.

This keeps the orchestration layer independent from model hosting.

## 10. Retries and fallbacks

Retry only failures that are safe to retry.

```text
timeout / transient provider failure
        ↓
retry same provider
        ↓
if policy allows
        ↓
fallback provider/model
        ↓
validate output again
```

Never assume a model fallback has equivalent quality; record the model used in the trace.

## 11. Model evaluation before promotion

Every candidate model must be benchmarked on:
- plan validity;
- schema adherence;
- tool-call accuracy;
- refusal of forbidden tools;
- reasoning quality;
- vision grounding where applicable;
- recovery decisions;
- latency;
- cost;
- stability over repeated runs.

A model becomes a production candidate only after passing role-specific thresholds.
