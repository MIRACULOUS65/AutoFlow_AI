# AutoFlow AI Backend — End-to-End Product Requirements Document

**Status:** Foundational implementation contract  
**Subsystem:** Backend / Control Plane  
**Product:** AutoFlow AI  
**Primary role:** Make the AI/ML execution engine usable, persistent, secure, observable, multi-tenant, and independent from the desktop UI.

---

## 1. Purpose

The backend is the authoritative control plane between the user-facing clients and the AI/ML execution system.

The backend must turn the AI/ML core into a real product boundary:

```text
Desktop / CLI / API Client
        |
        | HTTPS / WebSocket
        v
+----------------------------------------------------+
|                 AUTOFLOW BACKEND                   |
|                                                    |
| Auth + Tenant + Workspace + Policy                |
| Task + Plan + Approval + Execution                 |
| Agent + Model + Tool + Connector Registry          |
| Knowledge + Workflow Memory                        |
| Artifact + Audit + Observability                   |
| Queue + Workers + Scheduler                        |
+-------------------------+--------------------------+
                          |
            +-------------+-------------+
            |                           |
            v                           v
       AI/ML Runtime               External Systems
    models / RAG / agents       Gmail / browser / files
```

The backend is not the place where the LLM secretly owns the application. It is the place where requests, permissions, workflow state, tool access, approvals, and execution events are coordinated.

---

## 2. Product Outcome

A client should be able to call one endpoint with one natural-language objective and receive a durable execution ID.

Example:

```http
POST /api/v1/tasks
Authorization: Bearer <user-token>
Content-Type: application/json
```

```json
{
  "workspace_id": "ws_operations",
  "input": {
    "text": "Edit the attached Word file with the corrections I described, save the same file, create an email to the sender, attach the edited document, and ask me before sending."
  },
  "attachments": ["file_123"],
  "execution_mode": "autonomous_with_approval"
}
```

The response is not the final answer. It creates durable work:

```text
request
  ↓
task
  ↓
planning
  ↓
validation
  ↓
approval checkpoints
  ↓
execution
  ↓
verification
  ↓
recovery/replan when needed
  ↓
artifacts + external outcomes
  ↓
audit + workflow memory
```

---

## 3. Backend Principles

### 3.1 The backend is authoritative

The client is a presentation and interaction surface. The backend owns business rules and execution state.

### 3.2 Persistence before side effect

A material operation should have a persisted execution/step record before the side effect begins whenever practical.

### 3.3 Authorization before retrieval and execution

Authorization is not delegated to semantic search or the model.

### 3.4 Models propose, backend/runtime decides

The model can produce a plan or tool proposal. The backend validates schemas, policy, permissions, budget and approval requirements before execution.

### 3.5 Execution is eventful

Every meaningful state transition generates an immutable event. The current state is a materialized view over durable records/events.

### 3.6 Failures are first-class

A failure must become an explicit state with recovery metadata, not an exception swallowed into a fake success response.

### 3.7 Provider-independent model access

The backend must support multiple provider adapters, including API providers and self-hosted/open-weight model servers, without changing task semantics.

### 3.8 Desktop-independent operation

Every core operation must be testable through API/CLI workers without Electron.

---

## 4. Users, Organizations, Workspaces

The backend uses hierarchical tenancy:

```text
Organization
  ├── Users
  ├── Teams / Roles
  ├── Workspaces
  │    ├── Tasks
  │    ├── Agents
  │    ├── Tools
  │    ├── Connectors
  │    ├── Knowledge
  │    └── Workflows
  └── Policies
```

A request is evaluated with:

```text
principal
organization
workspace
roles
permissions
connector grants
tool grants
knowledge scopes
approval authority
policy profile
```

No task may execute with an empty or implicit security context.

---

## 5. End-to-End Task Lifecycle

```text
1. Authenticate
2. Resolve organization/workspace
3. Validate request
4. Store task
5. Store attachments / input references
6. Build execution context
7. Invoke AI/ML planner
8. Persist plan + version
9. Validate plan
10. Resolve approval checkpoints
11. Wait for approval when needed
12. Start execution
13. Run ready graph steps
14. Invoke agents/models
15. Validate tool proposals
16. Check permissions and policy
17. Execute connector/tool
18. Persist observation
19. Verify postconditions
20. Advance / recover / replan
21. Materialize artifacts
22. Persist final result
23. Emit audit summary
24. Persist eligible workflow memory
25. Stream status to clients
```

The backend must support the same workflow regardless of whether the caller is Electron, a REST client, a test harness, or a future mobile/web client.

---

## 6. Core Backend Domains

### 6.1 Identity and access

Owns login sessions, tokens, roles, permissions, connector grants, service identities and approval authority.

### 6.2 Tasks

Owns user intent, normalized request, task metadata, attachments, lifecycle state and user-visible outcome.

### 6.3 Planning

Stores planner output, plan versions, validation results and approval-bound hashes.

### 6.4 Execution

Owns execution attempts, step state, worker leases, checkpoints, event stream and recovery.

### 6.5 Agents

Stores agent definitions, capability declarations, allowed tools, model policy and runtime metadata.

### 6.6 Models

Stores provider/model registrations, capability metadata, health, cost/latency observations and deployment mode.

### 6.7 Tools and connectors

Stores tool definitions, permissions, scopes, connector state and execution policies.

### 6.8 Knowledge

Stores source metadata, chunks, ACL filters, embeddings and workflow memories.

### 6.9 Artifacts

Owns file metadata, blobs, hashes, provenance and verification state.

### 6.10 Audit and observability

Owns immutable audit records, correlation IDs, metrics and tracing metadata.

---

## 7. Task Model

A task is the durable representation of what the user wants.

Minimum fields:

```text
task_id
organization_id
workspace_id
created_by
input_text
normalized_intent
constraints
attachment_ids
execution_mode
risk_summary
state
created_at
updated_at
completed_at
```

A task does not directly contain transient worker state. Transient state belongs to execution/step records.

---

## 8. Execution Model

A task can have more than one execution over time.

Example:

```text
task_123
  ├── execution_001  FAILED (provider timeout)
  └── execution_002  COMPLETE
```

An execution binds a specific plan version and execution policy.

Minimum fields:

```text
execution_id
task_id
plan_id
plan_version
plan_hash
state
started_at
finished_at
initiated_by
worker_version
budget
```

---

## 9. Approval Requirements

Approval is a persisted object, not a UI-only concept.

Approval must bind to:

```text
execution_id
step_id
plan_version
action_hash
risk class
requested change
artifacts/evidence
approver identity
expiry
status
```

A material change after approval invalidates the approval.

Example:

```text
Draft email approved
       ↓
recipient changes
       ↓
action_hash changes
       ↓
old approval invalid
       ↓
new approval required
```

---

## 10. API Requirements

The public backend API must be versioned.

Required resource families:

```text
/auth
/organizations
/workspaces
/tasks
/plans
/agents
/models
/tools
/connectors
/knowledge
/workflows
/approvals
/executions
/artifacts
/audit
/health
```

The API must expose asynchronous task creation. A long-running task must not depend on one HTTP request remaining open.

---

## 11. API Task Creation Contract

```json
{
  "workspace_id": "ws_123",
  "input": {
    "text": "Create the report and email it to finance after I approve it."
  },
  "attachments": [],
  "constraints": {
    "deadline": null,
    "read_only": false
  },
  "execution_mode": "autonomous_with_approval"
}
```

Return:

```json
{
  "task_id": "task_123",
  "execution_id": "exec_123",
  "state": "PLANNING",
  "stream_url": "/api/v1/executions/exec_123/stream"
}
```

---

## 12. Provider and Open-Weight Model Integration

The backend must treat inference as a pluggable service.

Supported integration classes:

```text
Cloud provider adapter
OpenAI-compatible provider adapter
vLLM endpoint
Ollama endpoint
Other self-hosted inference endpoint
Embedding endpoint
Vision endpoint
Reranker endpoint
Future speech endpoint
```

The backend should not embed provider-specific semantics into task/execution records.

For open-weight deployments, the backend stores:

```text
provider_type = self_hosted
endpoint
model_id
capabilities
context_limit
supported_modalities
structured_output_support
tool_calling_support
health status
```

vLLM currently exposes an OpenAI-compatible HTTP server, making a generic OpenAI-compatible adapter a useful integration boundary. https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/

Gemma is an open-weight model family with variants intended for application deployment across laptops, desktops and servers, so model registration should not assume a cloud-only provider. https://ai.google.dev/gemma/docs

---

## 13. Knowledge and Context Service

The backend must assemble model context rather than dumping entire databases into prompts.

```text
USER REQUEST
   ↓
IDENTITY / ACL FILTER
   ↓
TASK CONTEXT
   ↓
SEMANTIC RETRIEVAL
   ↓
METADATA FILTER
   ↓
OPTIONAL RERANK
   ↓
WORKFLOW MEMORY
   ↓
CURRENT OBSERVATIONS
   ↓
CONTEXT BUDGETING
   ↓
MODEL REQUEST
```

The backend should support ChromaDB for local vector storage in the initial implementation. Vector similarity is not authorization; ACL filtering must occur as part of retrieval.

---

## 14. Workflow Memory

A completed task can create reusable memory only when:

```text
execution completed
AND
verification passed
AND
no unresolved safety incident
AND
artifact/result is trusted
AND
workspace policy permits learning
```

The backend stores semantic workflow structures rather than fixed UI coordinates.

Example:

```text
Find file named invoice report
Open document
Apply requested edits
Save existing document
Compose email to source sender
Attach artifact
Request approval
Send email
Verify delivery
```

---

## 15. Browser/Desktop Execution Boundary

Computer operations are delegated to execution workers/connectors.

Backend responsibility:

```text
authorize action
issue execution command
track lease
receive observation
persist event
request verification
recover or escalate
```

Backend does not assume that a click succeeded because a worker returned HTTP 200.

---

## 16. Scheduling and Automations

Automations are recurring task definitions, not copied prompt strings.

An automation contains:

```text
automation_id
workspace_id
owner
trigger
schedule/timezone
input template
execution policy
approval policy
enabled state
concurrency policy
last run
next run
```

A scheduler creates independent task executions for each run.

Example:

```text
Every Monday 09:00
      ↓
automation fires
      ↓
new task
      ↓
new execution
      ↓
existing workflow may be retrieved
      ↓
approval if required
      ↓
run
```

---

## 17. Concurrency

Independent tasks must execute concurrently without sharing mutable task state.

Isolation requirements:

```text
task context
variables
permissions
tool scope
execution state
artifacts
approval state
connector session
```

Shared immutable knowledge is allowed when access-controlled.

---

## 18. Backend Reliability

Required behavior:

- persistent state across worker restart;
- worker lease expiration;
- retry policy;
- idempotency keys;
- transaction boundaries;
- outbox/event delivery pattern;
- reconciliation jobs;
- dead-letter queue for irrecoverable messages;
- health checks;
- readiness checks;
- safe shutdown;
- graceful recovery from database/network outages.

---

## 19. Security Requirements

Minimum:

```text
TLS
short-lived access tokens
refresh/session controls
RBAC
workspace isolation
connector scope enforcement
server-side secrets
rate limits
request validation
content scanning where appropriate
prompt injection isolation
audit logging
safe file handling
sandbox boundaries
network egress policy
```

Provider API keys must never be sent to the desktop renderer.

---

## 20. Observability

Every execution must be traceable through:

```text
task_id
execution_id
step_id
agent_run_id
model_call_id
tool_call_id
observation_id
verification_id
approval_id
artifact_id
```

Log metadata, not hidden chain-of-thought.

---

## 21. Backend Test Requirements

The backend must be tested at several levels:

```text
contract
unit
integration
workflow
security
concurrency
failure/recovery
provider compatibility
browser/desktop adapter
load/endurance
migration/upgrade
```

The most important backend acceptance test is:

```text
Create task through API
→ plan
→ validate
→ approval pause
→ resume
→ execute
→ verify
→ artifact
→ final result
→ audit trail
```

---

## 22. Release Gates

A backend release is not ready because `/health` returns 200.

Required gates:

- schema and API compatibility pass;
- auth/tenant isolation pass;
- task lifecycle tests pass;
- execution persistence tests pass;
- approval binding tests pass;
- provider failover tests pass;
- tool permission tests pass;
- concurrency isolation tests pass;
- event stream/reconnect tests pass;
- artifact integrity tests pass;
- migration tests pass;
- recovery tests pass;
- security/adversarial tests pass.

---

## 23. Definition of Done

```text
[ ] API can create an execution from one prompt
[ ] Task and execution survive process restart
[ ] User/workspace authorization is enforced
[ ] Planner output is persisted and versioned
[ ] Plan validation is persisted
[ ] Approval is persisted and cryptographically/hash-bound to action context
[ ] Workers can resume interrupted executions
[ ] Models are provider-independent
[ ] Open-weight/self-hosted endpoints can be registered
[ ] ChromaDB retrieval is ACL-filtered
[ ] Tools are allowlisted and scoped
[ ] Tool results create observations
[ ] Material steps require verification
[ ] Recovery is bounded
[ ] Automations create isolated runs
[ ] Concurrent tasks do not leak state
[ ] Artifacts are durable and verified
[ ] Audit records are queryable
[ ] Desktop can consume live events without owning workflow logic
[ ] Full API-driven golden workflow passes without Electron
```

---

## 24. Implementation Order

```text
1. Repository + configuration
2. Database + migrations
3. Identity / tenancy
4. Task API
5. Plan persistence
6. Model gateway integration
7. Execution state machine
8. Queue/workers
9. Tool authorization
10. Approval service
11. Event streaming
12. Knowledge/RAG APIs
13. Workflow memory
14. Artifact service
15. Automations/scheduler
16. Browser/computer execution gateway
17. Observability/audit
18. Integration tests
19. Load/security tests
20. Desktop integration
```

The backend must stay aligned with the AI/ML rule that models propose structured actions while deterministic runtime components execute them. The AI/ML subsystem itself is designed to be independently testable before desktop work. fileciteturn4file0L65-L82
