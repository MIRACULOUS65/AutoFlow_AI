# AutoFlow AI Backend — System Architecture

## 1. Architecture Goal

The backend turns the AI/ML execution core into a durable control plane.

```text
                           CLIENTS
        +------------------+------------------+
        |                  |                  |
      Electron            CLI              REST/API
        |                  |                  |
        +------------------+------------------+
                           |
                       API Gateway
                           |
        +------------------+------------------+
        |                  |                  |
     Auth/Tenant        Tasks/Plans       Streaming
        |                  |                  |
        +------------------+------------------+
                           |
                  Orchestration Service
                           |
             +-------------+-------------+
             |             |             |
          Planner       Execution       Approval
             |             |             |
             +------+------+-------------+
                    |
              AI/ML Gateway
                    |
       +------------+-------------+
       |            |             |
   LLM Provider   Embeddings    Vision
       |
  cloud / open-weight / self-hosted

                    |
            Tool / Connector Layer
                    |
     +------+-------+------+--------+------+
     |      |       |      |        |      |
   Files Browser Desktop Gmail  Docs  Code

                    |
       +------------+-------------+
       |            |             |
   PostgreSQL     ChromaDB    Object Store
       |            |             |
       +------------+-------------+
                    |
           Audit + Telemetry
```

---

## 2. Logical Layers

### Layer A — Transport

REST/JSON for commands and queries. WebSocket/SSE for live execution events.

### Layer B — Application Services

Task, planning, approval, execution, knowledge, artifact, automation and identity services.

### Layer C — Domain State

Tasks, plans, workflows, executions, approvals, tool grants and audit data.

### Layer D — Infrastructure

PostgreSQL, Redis/queue, object storage, ChromaDB, telemetry, secret store.

### Layer E — AI/ML Integration

Provider adapters, model registry, planner/executor bridge, embeddings and optional vision/reranking services.

### Layer F — External Execution

Browser workers, desktop workers, connectors, API integrations and sandboxed code runners.

---

## 3. Service Boundaries

For the first implementation, these can be Python modules in one deployable backend. They must nevertheless have explicit interfaces.

```text
backend/
├── api/
├── auth/
├── orchestration/
├── executions/
├── approvals/
├── integrations/
├── knowledge/
├── artifacts/
├── audit/
├── db/
└── tests/
```

Later, high-load domains can be extracted into separate services without changing the public contract.

---

## 4. API Gateway

Responsibilities:

- authentication extraction;
- request ID creation;
- API versioning;
- rate limiting;
- body validation;
- idempotency key extraction;
- authorization middleware;
- routing;
- response normalization.

The gateway must not perform model inference directly.

---

## 5. Identity Flow

```text
CLIENT
  ↓
login / session
  ↓
identity provider
  ↓
access token
  ↓
backend middleware
  ↓
principal
  ↓
organization
  ↓
workspace
  ↓
roles + permissions
  ↓
request context
```

The request context becomes immutable for a single command unless an explicit privileged transition changes it.

---

## 6. Request Context

Canonical request context:

```python
RequestContext(
    request_id,
    trace_id,
    principal_id,
    organization_id,
    workspace_id,
    roles,
    permissions,
    connector_grants,
    tool_grants,
    knowledge_scopes,
    policy_profile,
    client_type,
)
```

The AI/ML engine receives a derived context object rather than direct database access.

---

## 7. Task Service

Responsibilities:

- create/read/update tasks;
- normalize attachments;
- reject malformed requests;
- enforce workspace membership;
- create execution records;
- expose status;
- expose user-facing results.

The service does not execute tools.

---

## 8. Planning Service

```text
Task
 ↓
Context assembler
 ↓
Planner request
 ↓
Model gateway
 ↓
Structured plan
 ↓
Schema validation
 ↓
Policy validation
 ↓
Persist plan version
 ↓
Approval analysis
```

A plan version includes a deterministic hash over its canonical serialized representation.

---

## 9. Execution Service

Execution is a stateful orchestration process.

```text
QUEUED
  ↓
PLANNING
  ↓
VALIDATING
  ↓
AWAITING_APPROVAL
  ↓
RUNNING
  ↓
VERIFYING
  ↓
COMPLETE
```

Failure transitions to recovery.

```text
VERIFYING
  ↓ failure
RECOVERY
  ├── RETRY
  ├── RE-OBSERVE
  ├── RE-RESOLVE
  ├── ALTERNATE
  ├── REPLAN
  └── HUMAN
```

This aligns with the AI/ML execution runtime contract. fileciteturn4file3L618-L669

---

## 10. Queue and Worker Architecture

Recommended model:

```text
API
 ↓
Persist command
 ↓
Outbox event
 ↓
Queue
 ↓
Execution worker
 ↓
Lease execution
 ↓
Perform one bounded unit of work
 ↓
Persist transition
 ↓
Emit event
 ↓
Continue / requeue
```

A worker must not hold exclusive responsibility for an execution forever.

Worker lease fields:

```text
worker_id
execution_id
lease_started_at
lease_expires_at
heartbeat_at
attempt
```

After lease expiry, reconciliation may requeue the work if no completion transaction exists.

---

## 11. Transactional Boundaries

### Create task

```text
validate request
→ transaction:
   task insert
   attachment links
   execution insert
   outbox event
→ commit
→ enqueue
```

### Complete tool step

```text
receive runtime result
→ transaction:
   step result
   observation
   verification result
   state transition
   audit event
   outbox event
→ commit
```

The side effect occurs outside the database transaction, therefore idempotency/reconciliation is required.

---

## 12. Outbox Pattern

External event delivery must not depend on a database transaction and queue operation succeeding simultaneously.

```text
DB TRANSACTION
 ├── business record
 └── outbox event

COMMIT
   ↓
outbox dispatcher
   ↓
message broker / stream
```

The dispatcher can retry safely because events have stable IDs.

---

## 13. Event Model

Canonical event:

```json
{
  "event_id": "evt_123",
  "type": "execution.step.completed",
  "organization_id": "org_1",
  "workspace_id": "ws_1",
  "task_id": "task_1",
  "execution_id": "exec_1",
  "step_id": "step_2",
  "occurred_at": "2026-09-12T10:00:00Z",
  "actor_type": "worker",
  "actor_id": "worker_7",
  "schema_version": 1,
  "data": {}
}
```

Events must not contain secret values or hidden chain-of-thought.

---

## 14. Model Gateway Architecture

```text
Agent request
   ↓
Capability resolver
   ↓
Model registry
   ↓
Policy filter
   ↓
Health / latency / cost scorer
   ↓
Provider adapter
   ↓
Model endpoint
   ↓
Normalized response
```

Provider adapter interface:

```python
class ModelProvider(Protocol):
    async def chat(self, request) -> ModelResponse: ...
    async def stream(self, request): ...
    async def embeddings(self, request) -> EmbeddingResponse: ...
    async def health(self) -> ProviderHealth: ...
```

Open-weight model servers are treated exactly like any other provider once they expose the required contract. vLLM is one current example of an inference server implementing OpenAI-style APIs. citeturn725794search2turn725794search8

---

## 15. Model Registry

Each model record should include:

```text
model_id
provider_id
endpoint
model_name
version
modalities
context_limit
supports_json
supports_tools
supports_vision
supports_embeddings
supports_streaming
status
cost_input
cost_output
latency_p50
latency_p95
quality_score
last_health_check
```

Model routing must be capability-based, not hard-coded in agents.

---

## 16. ChromaDB Architecture

Initial design:

```text
Knowledge ingestion
  ↓
parse
  ↓
chunk
  ↓
metadata
  ↓
embedding
  ↓
ChromaDB
```

Retrieval:

```text
query
 ↓
workspace/tenant ACL filter
 ↓
embedding
 ↓
Chroma similarity search
 ↓
metadata filtering
 ↓
optional rerank
 ↓
context pack
```

Metadata should include:

```text
tenant_id
workspace_id
source_id
document_id
permissions_scope
chunk_id
version
content_type
created_at
trust_level
```

---

## 17. Context Assembly Service

The model should not receive every available memory item.

Context is assembled into ordered sections:

```text
SYSTEM POLICY
TASK OBJECTIVE
CURRENT STATE
AUTHORIZED CONTEXT
RETRIEVED KNOWLEDGE
RELEVANT WORKFLOW MEMORY
TOOL DEFINITIONS
RECENT OBSERVATIONS
RECOVERY HISTORY
OUTPUT CONTRACT
```

Context assembler responsibilities:

- token budgeting;
- deduplication;
- relevance scoring;
- ACL enforcement;
- provenance attachment;
- freshness selection;
- truncation strategy;
- priority preservation.

---

## 18. Connector Architecture

Connector is the backend integration boundary to a real external system.

```text
ConnectorDefinition
 ├── id
 ├── provider
 ├── authentication_type
 ├── scopes
 ├── health_check
 ├── capabilities
 └── tool_factory
```

Examples:

```text
Gmail
Google Drive
Slack
GitHub
Browser
Windows Desktop
Filesystem
HTTP REST
SMTP
```

A connector should expose narrowly scoped tools rather than one universal `execute()` function.

---

## 19. Tool Registry

The registry maps semantic tool names to executable implementations.

```text
email.create_draft
email.attach
email.send
files.read
files.write
docx.open
docx.replace_text
docx.save
browser.navigate
browser.find
browser.click
browser.type
```

Each tool declares:

```text
risk
permissions
input schema
output schema
idempotency
timeout
verifier
connector
```

---

## 20. Approval Architecture

```text
Execution step
 ↓
risk evaluation
 ↓
approval required?
 ├── no → continue
 └── yes
      ↓
create approval
      ↓
persist + notify
      ↓
AWAITING_APPROVAL
      ↓
approve / reject / expire
      ↓
continue or terminate
```

Approvals must be invalidated on material plan/action changes.

---

## 21. Artifact Architecture

Artifacts use object storage for bytes and PostgreSQL for metadata.

```text
artifact metadata → PostgreSQL
artifact bytes    → object storage
verification      → execution/verification tables
```

Artifact hash is calculated on final bytes.

---

## 22. Automation Scheduler

The scheduler should create tasks; it should not implement task logic.

```text
Automation definition
 ↓
scheduler tick
 ↓
create task
 ↓
create execution
 ↓
normal orchestrator
```

This means scheduled workflows and manual workflows use the same execution engine.

---

## 23. Health Model

Three health concepts:

```text
liveness  = process is alive
readiness = dependencies available
functional health = core task path works
```

Model provider health must be tracked independently from backend health.

---

## 24. Disaster Recovery

Required backups:

```text
PostgreSQL
object storage
Chroma collections / persistence
configuration
migration history
```

Recovery target:

```text
restore DB
restore artifacts
restore vector store
restart workers
rebuild projections if necessary
resume/reconcile in-flight executions
```

---

## 25. Deployment Topology

Development:

```text
Docker Compose
├── backend
├── postgres
├── redis
├── chroma
└── object store
```

Production starting point:

```text
reverse proxy
  ↓
backend replicas
  ↓
PostgreSQL
Redis/queue
ChromaDB or vector service
object storage
model endpoints
worker pool
```

Inference servers can be separated from the application backend so model scaling does not require API service scaling.

---

## 26. Failure Domains

The system must treat failures independently:

```text
client failure
API process failure
database failure
queue failure
worker failure
model provider failure
connector failure
browser failure
desktop worker failure
vector DB failure
object store failure
```

A failure in one domain must not silently corrupt state in another.

---

## 27. Security Architecture

Use layered controls:

```text
TLS
 ↓
Auth
 ↓
RBAC
 ↓
Workspace ACL
 ↓
Tool scope
 ↓
Risk policy
 ↓
Approval
 ↓
Execution sandbox
 ↓
Audit
```

Secrets live in environment/secret-management systems and connector-specific secure storage, not the React renderer.

---

## 28. Architectural Invariants

```text
1. Backend owns execution state.
2. Client cannot directly perform privileged server actions.
3. No tool call without permission.
4. No material completion without verification.
5. No approval reuse after material action mutation.
6. No cross-tenant retrieval.
7. No provider key in renderer.
8. No infinite worker loop.
9. Every execution is traceable.
10. Scheduled and manual work share the same execution engine.
```
