# AutoFlow AI — Backend Control Plane PRD

**Status:** Implementation-ready  
**Scope:** Backend / API / Control Plane  
**AI/ML Dependency:** None for initial implementation  
**Primary Stack:** FastAPI + Python + Pydantic + PostgreSQL + Redis  
**Client:** Electron + Next.js desktop application  
**Primary principle:** Build the backend so the real orchestrator and agents can be plugged in later without rewriting the API, database model, or frontend.

---

# 1. Executive Summary

AutoFlow AI is an agentic execution platform whose central promise is:

> **Turn one instruction into a verified workflow.**

The desktop application is the human-facing command center. The backend is the authoritative control plane. The AI/ML runtime is the intelligence layer. Deterministic tools are the execution layer.

The backend therefore should not attempt to become the AI.

Its job is to provide a durable system through which:

```text
User Goal
   ↓
Task
   ↓
Plan
   ↓
Execution
   ↓
Steps
   ↓
Approvals / Policy
   ↓
Tool Actions
   ↓
Observations
   ↓
Verification
   ↓
Recovery / Replanning
   ↓
Artifacts
   ↓
Audit
```

can be represented, persisted, controlled, observed, and resumed.

The backend must be runnable immediately with:

```text
Mock Orchestrator
Mock Agents
Mock Tools
Mock Verifier
Mock Policy
```

while the ML teammates independently develop:

```text
Real Orchestrator
Real Agent Runtime
Model Gateway
Agent-specific reasoning
```

This means backend development can proceed **now**, without waiting for AI/ML completion.

---

# 2. Product Architecture

AutoFlow has four major planes:

```text
┌──────────────────────────────────────────────┐
│ HUMAN PLANE                                  │
│ Electron / Desktop / Approvals / Composer    │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ CONTROL PLANE                                │
│ Auth / Tenancy / Tasks / State / Policy      │
│ Approvals / Audit / Events / Orchestration   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ INTELLIGENCE PLANE                           │
│ Orchestrator / Agents / Models / RAG         │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ EXECUTION PLANE                              │
│ APIs / Files / Browser / Desktop / Sandbox   │
└──────────────────────────────────────────────┘
```

This separation is fundamental to AutoFlow's architecture.

The backend PRD covers the **Control Plane**, plus the interfaces needed to safely connect it to the other planes.

---

# 3. Backend Mission

The backend must answer:

```text
Who requested this?
Which organization?
Which workspace?
What task exists?
What plan is being executed?
What state is it in?
What is allowed?
What requires approval?
What has happened?
What was verified?
What failed?
What should happen next?
What artifacts were created?
Who approved it?
What is the complete audit trail?
```

It must **not** answer these questions by embedding model reasoning.

For example, the backend should never implement:

```python
if "weekly report" in goal:
    use_spreadsheet_agent()
```

That is intelligence-layer logic.

Instead:

```text
API
 ↓
Task
 ↓
Orchestrator interface
 ↓
Plan
 ↓
Execution Controller
```

The orchestrator decides the plan.

The backend controls and persists it.

---

# 4. Goals

## G1 — Stable API boundary

Provide a versioned REST API and event stream usable by the existing Electron frontend.

## G2 — Durable execution state

Execution state must survive:

- backend restart;
- worker crash;
- desktop disconnect;
- API retry;
- worker replacement;
- later browser/application failures.

The execution engine specification explicitly requires persisted execution state rather than worker-memory state.

## G3 — Contract-first architecture

All cross-system communication must use explicit typed contracts.

## G4 — Async execution

Long-running workflows must not block the request that created them.

The architecture explicitly specifies:

```text
POST /tasks
    ↓
persist
    ↓
queue
    ↓
worker
    ↓
events
    ↓
SSE/WebSocket
    ↓
desktop
```



## G5 — First-class approvals

Approval must be a durable workflow state, not merely a frontend modal.

## G6 — Secure multi-tenancy

Every task, execution, artifact, event, and approval must respect organization/workspace boundaries.

## G7 — AI/ML independence

The backend must operate entirely with mocks.

## G8 — Frontend compatibility

The backend objects should map directly onto the frontend's Task, Execution, Approval, Artifact, Workflow, Agent, Knowledge and Event models.

## G9 — Extensibility

New agents, tools, verifiers, connectors and model providers must be pluggable.

## G10 — Auditable execution

Every material action and state transition must be traceable.

---

# 5. Non-Goals

This phase does not implement:

- model training;
- prompt engineering;
- real model providers;
- real agent reasoning;
- RAG algorithms;
- browser automation;
- Windows UI automation;
- real email sending;
- production connectors;
- arbitrary shell execution;
- unrestricted code execution;
- visual grounding;
- production workflow memory.

Mocks are acceptable and expected.

---

# 6. Architectural Rule: No Hardcoded AI

This is one of the most important rules in the entire project.

The backend must not contain:

```text
agent-specific prompts
provider-specific model calls
goal-specific branching
LLM chain logic
hardcoded tool selection
hardcoded workflow recipes
```

Instead use interfaces.

Example:

```python
class Orchestrator:
    async def create_plan(
        self,
        task: TaskRequest
    ) -> Plan:
        ...
```

Development implementation:

```python
MockOrchestrator
```

Later:

```python
RealOrchestrator
```

The API remains unchanged.

Likewise:

```python
class AgentRuntime:
    async def run_step(
        self,
        request: AgentRunRequest
    ) -> AgentRunResult:
        ...
```

This means your ML teammates can work independently.

---

# 7. Technology Stack

The existing project PRD specifies:

```text
FastAPI / async Python
Pydantic / JSON Schema
PostgreSQL
Redis / queue
```



Recommended implementation:

```text
Python 3.12+
FastAPI
Uvicorn
Pydantic v2
SQLAlchemy 2.x
Alembic
PostgreSQL
Redis
pytest
httpx
Ruff
mypy / pyright
structured logging
OpenTelemetry-compatible tracing
```

The exact libraries can change.

The contracts should not.

---

# 8. Backend Repository

Recommended structure:

```text
backend/
│
├── app/
│   ├── main.py
│
│   ├── api/
│   │   └── v1/
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── workspaces.py
│   │       ├── tasks.py
│   │       ├── plans.py
│   │       ├── executions.py
│   │       ├── approvals.py
│   │       ├── artifacts.py
│   │       ├── events.py
│   │       ├── agents.py
│   │       ├── workflows.py
│   │       ├── knowledge.py
│   │       └── health.py
│
│   ├── domain/
│   ├── schemas/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── orchestration/
│   ├── agents/
│   ├── tools/
│   ├── verification/
│   ├── recovery/
│   ├── workers/
│   └── db/
│
├── tests/
│   ├── unit/
│   ├── api/
│   ├── integration/
│   └── contract/
│
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

---

# 9. Layering

Use strict boundaries:

```text
API
 ↓
Application Services
 ↓
Domain
 ↓
Repositories
 ↓
Database
```

External intelligence:

```text
Application Services
 ↓
Orchestrator Interface
Agent Interface
Verifier Interface
Tool Interface
Policy Interface
```

Do not let FastAPI route handlers directly manipulate SQLAlchemy objects everywhere.

Routes should remain thin.

---

# 10. Core Domain Objects

The backend must support:

```text
Organization
User
Membership
Workspace

Task
TaskAttachment

Plan
PlanStep

Execution
ExecutionStepState

Approval
ApprovalEvidence

Event

Artifact

VerificationRun
VerificationCheck

RecoveryRun

Workflow
WorkflowVersion

Agent
AgentVersion

KnowledgeSource

AuditRecord

IdempotencyRecord
```

---

# 11. Organization

Tenant boundary.

```text
organization_id
name
status
created_at
updated_at
```

Example:

```json
{
  "id": "org_01",
  "name": "Acme Corporation",
  "status": "ACTIVE"
}
```

---

# 12. Workspace

A workspace provides logical isolation within an organization.

```text
workspace_id
organization_id
name
policy_profile
status
created_at
updated_at
```

Example:

```json
{
  "id": "ws_01",
  "organization_id": "org_01",
  "name": "Operations",
  "policy_profile": "standard"
}
```

---

# 13. User and Membership

User:

```text
user_id
email
display_name
status
created_at
```

Membership:

```text
user_id
organization_id
workspace_id
role
status
```

Initial roles:

```text
OWNER
ADMIN
OPERATOR
VIEWER
```

Permissions must be centralized.

Do not scatter:

```python
if user.role == ...
```

through every endpoint.

---

# 14. Task

A Task represents the user's desired outcome.

```text
Task
├── task_id
├── organization_id
├── workspace_id
├── created_by
├── goal
├── normalized_goal
├── constraints[]
├── attachments[]
├── priority
├── status
├── current_plan_version
├── current_execution_id
├── created_at
├── updated_at
├── started_at
├── completed_at
└── failure_reason
```

The architecture explicitly defines a request boundary around identity, organization, workspace, goal, attachments, constraints, client metadata, and policy profile.

---

# 15. Task State

Canonical states:

```text
QUEUED
PLANNING
VALIDATING
AWAITING_APPROVAL
RUNNING
VERIFYING
COMPLETE
```

Failure/recovery:

```text
RECOVERY
RETRY
RE-OBSERVE
RE-RESOLVE
ALTERNATE_PATH
REPLAN
HUMAN_ESCALATION
```

Terminal states:

```text
FAILED
CANCELLED
EXPIRED
BLOCKED
```

These states are already established in the project's execution design.

The backend must enforce legal state transitions.

---

# 16. State Machine

Create one authoritative state machine.

Example:

```python
transition(
    execution_id,
    from_state=RUNNING,
    to_state=VERIFYING
)
```

The transition service checks:

```text
current state
allowed transition
approval requirements
policy
cancellation
expiry
execution invariants
```

No endpoint should manually change status fields.

Bad:

```python
execution.status = "COMPLETE"
```

Good:

```python
state_machine.complete_execution(...)
```

---

# 17. Plan

A Plan is an immutable workflow version generated by the orchestrator.

```text
plan_id
task_id
version
graph
generated_by
created_at
validation_status
risk_summary
required_approvals
plan_hash
```

Plans are immutable.

If the orchestrator replans:

```text
Plan v1
Plan v2
Plan v3
```

Never mutate v1 into v2.

---

# 18. Task Step

Every material step contains:

```text
step_id
objective
dependencies[]
agent_profile
allowed_tools[]
inputs
expected_state
preconditions[]
verification_checks[]
risk_class
timeout
retry_policy
recovery_budget
status
```

The execution-engine specification explicitly defines this contract.

---

# 19. Execution

An execution is one concrete attempt to run a plan.

```text
execution_id
task_id
plan_id
plan_version
status
current_step_id
attempt_count
cancel_requested
started_at
ended_at
budget
created_at
updated_at
```

Each execution gets an isolated context:

```text
workspace scope
permission snapshot
policy snapshot
context namespace
tool allowlist
artifact namespace
budget
```

That isolation is explicitly part of the system architecture.

---

# 20. Durable Execution

Persist at minimum:

```text
task
plan
plan version
step states
execution state
attempts
approval state
artifacts
events
verification results
recovery history
```

A worker may crash after a tool call.

The system must resume from durable state rather than blindly replaying completed side effects.

---

# 21. Idempotency

Support request-level idempotency:

```http
Idempotency-Key: task-create-123
```

For execution actions:

```text
execution_id
+
step_id
+
logical_action
```

The execution engine already specifies stable idempotency keys for side-effect actions.

This protects against:

```text
network timeout
client retry
worker retry
duplicate job delivery
```

---

# 22. Approval

Approval is a first-class persisted object.

```text
approval_id
execution_id
plan_version
action_hash
requested_by
approver
risk_class
summary
evidence[]
expires_at
status
decision_timestamp
```

This structure is already defined in the project PRD.

Statuses:

```text
PENDING
APPROVED
REJECTED
EXPIRED
INVALIDATED
```

---

# 23. Approval Invariant

The most important rule:

> A previous approval becomes invalid if the material action changes.

The project architecture explicitly requires this.

Therefore:

```text
Approval
   ↓
Plan v3 + Action Hash A
```

cannot authorize:

```text
Plan v3 + Action Hash B
```

---

# 24. Action Hash

For a material action construct a canonical representation:

```text
tool
arguments
target
recipient
resource
plan_version
```

Hash it.

Before executing an approved action:

```text
recompute hash
        ↓
compare
        ↓
match → allowed
different → invalidate approval
```

This makes approval cryptographically bound to the intended operation.

---

# 25. Event Architecture

Every important workflow transition generates a durable event.

Initial event catalog:

```text
task.created
task.updated
task.cancel_requested

plan.created
plan.validated
plan.invalid

execution.started
execution.paused
execution.resumed
execution.completed
execution.failed
execution.cancelled

step.started
step.completed

approval.requested
approval.granted
approval.rejected
approval.expired

tool.requested
tool.started
tool.completed

observation.created

verification.started
verification.passed
verification.failed

recovery.started
recovery.replanned

artifact.created
```

The execution specification already defines this event model.

---

# 26. Event Correlation

Every event should carry:

```text
event_id
task_id
execution_id
step_id
agent_run_id
model_call_id
tool_call_id
verification_id
trace_id
sequence
timestamp
```

Correlation:

```text
Task
 ↓
Execution
 ↓
Step
 ↓
Agent Run
 ↓
Model Call
 ↓
Tool Call
 ↓
Verification
```

---

# 27. Event Sequence

Every execution receives a monotonically increasing sequence:

```text
1 task.created
2 execution.started
3 plan.created
4 plan.validated
5 step.started
6 tool.started
7 tool.completed
8 verification.started
9 verification.passed
...
```

Why?

The Electron client may disconnect.

When it reconnects:

```http
GET /events?after=42
```

the backend can return events 43 onward.

This avoids relying only on live WebSocket state.

---

# 28. Realtime Transport

Recommended initial design:

```text
REST → commands
SSE  → server → desktop events
```

Example:

```http
GET /api/v1/executions/{execution_id}/events
```

Response:

```text
event: step.started
data: {...}

event: verification.passed
data: {...}
```

WebSocket can be introduced later if genuine bidirectional realtime requirements emerge.

---

# 29. Task API

## Create

```http
POST /api/v1/tasks
```

Request:

```json
{
  "workspace_id": "ws_01",
  "goal": "Create my weekly operations report",
  "constraints": [],
  "attachments": [],
  "client_metadata": {
    "source": "desktop"
  }
}
```

Response:

```json
{
  "task_id": "task_01",
  "execution_id": "exec_01",
  "status": "QUEUED"
}
```

The server returns quickly.

Planning happens asynchronously.

---

# 30. Task APIs

```http
POST /api/v1/tasks

GET /api/v1/tasks

GET /api/v1/tasks/{task_id}

POST /api/v1/tasks/{task_id}/cancel
```

Filters:

```text
workspace
status
creator
search
date
priority
```

---

# 31. Execution APIs

```http
GET /api/v1/executions

GET /api/v1/executions/{execution_id}

POST /api/v1/executions/{execution_id}/pause

POST /api/v1/executions/{execution_id}/resume

POST /api/v1/executions/{execution_id}/cancel

GET /api/v1/executions/{execution_id}/events
```

Every command must pass through the state machine.

---

# 32. Approval APIs

```http
GET /api/v1/approvals

GET /api/v1/approvals/{approval_id}

POST /api/v1/approvals/{approval_id}/approve

POST /api/v1/approvals/{approval_id}/reject
```

Approval mutation requires:

```text
authentication
permission
pending state
not expired
plan still valid
action hash still valid
workspace match
```

---

# 33. Plan APIs

```http
GET /api/v1/tasks/{task_id}/plans

GET /api/v1/tasks/{task_id}/plans/{version}
```

Plans are read-only from the desktop.

The desktop cannot make an arbitrary plan authoritative.

---

# 34. Artifact APIs

```http
GET /api/v1/artifacts

GET /api/v1/artifacts/{artifact_id}

GET /api/v1/artifacts/{artifact_id}/download
```

Initial artifact types:

```text
DOCX
XLSX
PPTX
PDF
CSV
JSON
CODE
IMAGE
TEST_REPORT
EMAIL_DRAFT
MESSAGE_DRAFT
```

Artifact metadata follows the existing product design.

---

# 35. Workflow APIs

```http
GET /api/v1/workflows

GET /api/v1/workflows/{workflow_id}

GET /api/v1/workflows/{workflow_id}/versions

GET /api/v1/workflows/{workflow_id}/runs
```

Workflow versions are immutable.

---

# 36. Agent APIs

The backend only exposes agent registry information.

```http
GET /api/v1/agents

GET /api/v1/agents/{agent_id}
```

Agent:

```text
agent_id
name
description
capabilities[]
supported_tools[]
status
version
```

The backend must not contain the agent's reasoning.

---

# 37. Knowledge APIs

Initial read APIs:

```http
GET /api/v1/knowledge/sources

GET /api/v1/knowledge/sources/{source_id}
```

Real indexing/retrieval can remain mocked.

Critically:

```text
similarity ≠ authorization
```

The existing architecture explicitly requires authorization independently of retrieval relevance.

---

# 38. Orchestrator Interface

The most important interface between you and ML teammate #2:

```python
class Orchestrator(Protocol):

    async def create_plan(
        self,
        request: TaskRequest
    ) -> Plan:
        ...

    async def replan(
        self,
        request: ReplanRequest
    ) -> PlanFragment:
        ...
```

Backend responsibility:

```text
receive task
→ call orchestrator
→ validate returned plan
→ persist plan
→ calculate control metadata
→ move execution forward
```

Orchestrator responsibility:

```text
understand goal
→ decompose
→ determine dependencies
→ assign agents
→ generate structured plan
```

---

# 39. Agent Runtime Interface

The most important interface between you and ML teammate #1:

```python
class AgentRuntime(Protocol):

    async def run_step(
        self,
        request: AgentRunRequest
    ) -> AgentRunResult:
        ...
```

Input:

```text
task
execution
step
objective
inputs
allowed tools
expected state
verification requirements
budget
policy context
```

Output:

```text
agent_run_id
status
proposed actions
observations
output
telemetry
```

---

# 40. Tool Runtime Interface

Agents should propose actions.

They do not directly execute them.

```python
class ToolRuntime(Protocol):

    async def execute(
        self,
        call: ToolCall
    ) -> ToolResult:
        ...
```

Execution sequence:

```text
Agent
 ↓
ToolCall JSON
 ↓
Schema Validation
 ↓
Policy Validation
 ↓
Permission Validation
 ↓
Idempotency
 ↓
Tool Runtime
 ↓
Side Effect
```

The execution engine explicitly establishes this separation.

---

# 41. Verification Interface

```python
class Verifier(Protocol):

    async def verify(
        self,
        request: VerificationRequest
    ) -> VerificationResult:
        ...
```

Types:

```text
STRUCTURAL
SEMANTIC
UI_STATE
DATA
ARTIFACT
```

Verification result:

```json
{
  "status": "passed",
  "checks": [
    {
      "id": "artifact_exists",
      "passed": true
    },
    {
      "id": "content_valid",
      "passed": true
    }
  ],
  "evidence": [
    "artifact://report.xlsx"
  ]
}
```

The project defines verification specifically because:

> **Tool success ≠ business success.**



---

# 42. Recovery Interface

```python
class RecoveryManager(Protocol):

    async def recover(
        self,
        request: RecoveryRequest
    ) -> RecoveryDecision:
        ...
```

Possible results:

```text
RETRY
REOBSERVE
RERESOLVE
ALTERNATE_PATH
REPLAN
HUMAN_ESCALATION
FAIL
```

Recovery must be bounded by:

```text
attempt budget
time budget
model-call budget
replan budget
tool-cost budget
```

The architecture explicitly forbids infinite agent loops.

---

# 43. Policy Engine

Policy must be a separate interface.

```python
class PolicyEngine(Protocol):

    async def evaluate(
        self,
        actor,
        workspace,
        action,
        resource,
        context
    ) -> PolicyDecision:
        ...
```

Result:

```json
{
  "allowed": false,
  "requires_approval": true,
  "risk_class": "HIGH",
  "reason": "External communication requires explicit approval"
}
```

Policy can be mocked in this phase.

---

# 44. Authorization Flow

Every consequential operation:

```text
Authenticate
 ↓
Resolve organization
 ↓
Resolve workspace
 ↓
Authorize
 ↓
Evaluate policy
 ↓
Check approval
 ↓
Execute
 ↓
Audit
```

This matches the project's security principle:

```text
authenticate
↓
authorize
↓
scope
↓
validate
↓
approve
↓
execute
↓
audit
```



---

# 45. Execution Context Snapshot

When execution starts, persist:

```text
organization
workspace
permissions
policy profile
tool allowlist
budget
context namespace
```

The snapshot gives the execution a deterministic context.

This is especially important when user permissions or workspace policy later change.

---

# 46. Worker Architecture

Initial architecture:

```text
FastAPI
   ↓
Redis Queue
   ↓
Worker
   ↓
Execution Controller
   ↓
Orchestrator / Agent / Tools / Verifier
```

Worker responsibilities:

```text
load durable state
check cancellation
check expiry
load next step
invoke interface
persist result
emit event
```

The worker must be stateless beyond temporary execution of a job.

---

# 47. Queue

Redis may be used for:

```text
planning jobs
execution jobs
resume jobs
recovery jobs
replanning jobs
transient locks
```

However:

> Redis is not the authoritative workflow database.

PostgreSQL owns durable state.

---

# 48. Worker Crash Scenario

Suppose:

```text
Step 4
   ↓
tool starts
   ↓
worker crashes
```

On restart the worker:

```text
load execution
↓
load persisted step state
↓
determine whether side effect was committed
↓
use idempotency/observation
↓
resume safely
```

It must not blindly execute Step 4 again.

---

# 49. Cancellation

Cancellation:

```text
POST /tasks/{id}/cancel
        ↓
persist cancel_requested
        ↓
emit event
        ↓
worker observes flag
        ↓
stop before next side effect
        ↓
CANCELLED
```

Cancellation itself must be durable.

The execution engine explicitly requires workers to check cancellation before initiating another side effect where possible.

---

# 50. Concurrency

Independent executions must never share mutable execution state.

Isolation:

```text
context
variables
permissions
events
artifacts
locks
```

Example:

```text
Execution A → RUNNING
Execution B → AWAITING_APPROVAL
Execution C → RUNNING
```

Execution A must never modify B's state.

---

# 51. Database

PostgreSQL is the authoritative state store.

Recommended tables:

```text
organizations
users
organization_memberships
workspaces
workspace_memberships

tasks
task_attachments

task_plans
task_steps

executions
execution_step_states
execution_context_snapshots
execution_budgets

approvals
approval_evidence

events

verification_runs
verification_checks

recovery_runs

artifacts
artifact_sources

workflows
workflow_versions

agents
agent_versions

knowledge_sources

audit_logs

idempotency_keys
```

The system architecture already places PostgreSQL as the authoritative metadata/state layer.

---

# 52. Database Indexes

At minimum:

```text
tasks(workspace_id, created_at)
tasks(workspace_id, status)

executions(task_id, created_at)
executions(workspace_id, status)

events(execution_id, sequence)

approvals(workspace_id, status)

artifacts(execution_id)

audit_logs(workspace_id, timestamp)
```

Use UUID/UUIDv7-like IDs.

Use UTC timestamps.

---

# 53. JSONB

Use JSONB for genuinely extensible structures:

```text
constraints
agent metadata
tool arguments
event payloads
verification evidence
policy metadata
```

Do not turn the entire database into arbitrary JSON.

Core relationships should remain relational.

---

# 54. API Versioning

All public endpoints:

```text
/api/v1/...
```

Breaking API contracts require:

```text
/api/v2/...
```

Do not silently modify response structures.

---

# 55. Standard Error Envelope

All errors:

```json
{
  "error": {
    "code": "INVALID_STATE_TRANSITION",
    "message": "Execution cannot transition from COMPLETE to RUNNING.",
    "request_id": "req_01"
  }
}
```

Core error codes:

```text
VALIDATION_ERROR
UNAUTHENTICATED
FORBIDDEN
NOT_FOUND
CONFLICT
INVALID_STATE_TRANSITION
APPROVAL_REQUIRED
APPROVAL_INVALID
POLICY_DENIED
TOOL_NOT_ALLOWED
EXECUTION_FAILED
VERIFICATION_FAILED
RECOVERY_EXHAUSTED
CANCELLED
EXPIRED
INTERNAL_ERROR
```

---

# 56. Health APIs

```http
GET /health
GET /ready
GET /version
```

`/health`:

```text
process is alive
```

`/ready`:

```text
database reachable
queue reachable
required dependencies available
```

`/version`:

```text
backend version
API version
contract version
```

---

# 57. Authentication

Initial mode may use mocked/local authentication.

Contract:

```http
Authorization: Bearer <token>
```

Resolved context:

```text
user_id
organization_id
workspace_id
roles
```

Later:

```text
real identity provider
```

can replace it.

The rest of the backend should not need to change.

---

# 58. Multi-Tenant Enforcement

Every repository query for scoped data must include the scope.

Bad:

```python
get_task(task_id)
```

Better:

```python
get_task(
    task_id,
    organization_id,
    workspace_id
)
```

Cross-tenant access should resolve as not found or unauthorized.

Never assume that knowing an opaque task ID grants access.

---

# 59. Attachment Contract

Do not put arbitrary file bytes directly into task JSON.

Initial metadata:

```text
attachment_id
filename
mime_type
size
content_hash
source
```

Later the system can introduce:

```text
upload sessions
object storage
signed URLs
chunked uploads
```

---

# 60. Artifact Storage

The database stores metadata.

Large binary objects belong in object storage.

Architecture:

```text
PostgreSQL
  ↓
artifact metadata

Object Storage
  ↓
artifact bytes
```

During local development:

```text
local filesystem fixture
```

is acceptable.

---

# 61. Task Creation — Detailed Sequence

```text
1. Desktop calls POST /tasks
2. Authenticate request
3. Resolve organization
4. Resolve workspace
5. Authorize task creation
6. Validate schema
7. Validate attachments
8. Create Task = QUEUED
9. Create Execution
10. Snapshot policy/permissions
11. Persist transaction
12. Emit task.created
13. Enqueue planning job
14. Return task_id + execution_id
```

The API returns immediately.

AI reasoning happens later.

---

# 62. Planning Sequence

```text
Worker
 ↓
load execution
 ↓
QUEUED → PLANNING
 ↓
Orchestrator.create_plan()
 ↓
validate Plan schema
 ↓
persist Plan version
 ↓
plan.created
 ↓
PLANNING → VALIDATING
 ↓
deterministic validation
 ↓
plan.validated
 ↓
approval detection
```

Then:

```text
approval required → AWAITING_APPROVAL
```

or:

```text
no approval → RUNNING
```

---

# 63. Execution Sequence

```text
load runnable step
        ↓
check cancellation
        ↓
check expiry
        ↓
load permissions
        ↓
load policy
        ↓
invoke AgentRuntime
        ↓
receive structured action
        ↓
validate action schema
        ↓
policy validation
        ↓
permission validation
        ↓
ToolRuntime
        ↓
Observation
        ↓
Verifier
```

Success:

```text
next step
```

Failure:

```text
RecoveryManager
```

---

# 64. Completion

A task reaches `COMPLETE` only if:

```text
all required steps completed
AND
material verification passed
AND
approvals are valid
AND
not cancelled
AND
not expired
AND
final outcome requirements satisfied
```

The system must never mark a task successful simply because a tool returned HTTP 200 or an automation API returned success.

---

# 65. Recovery

Example:

```text
A ✓
B ✓
C ✗
D pending
E pending
```

Do not blindly regenerate:

```text
A → B → C → D → E
```

Instead:

```text
C
 ↓
recovery
 ↓
alternate path / replan
 ↓
D
 ↓
E
```

This partial-replanning behavior is explicitly part of the execution architecture.

---

# 66. Event Examples

## Task created

```json
{
  "type": "task.created",
  "task_id": "task_01",
  "execution_id": "exec_01",
  "sequence": 1
}
```

## Approval requested

```json
{
  "type": "approval.requested",
  "task_id": "task_01",
  "execution_id": "exec_01",
  "plan_version": 3,
  "action_hash": "sha256:...",
  "risk_class": "HIGH"
}
```

## Verification passed

```json
{
  "type": "verification.passed",
  "execution_id": "exec_01",
  "step_id": "step_04",
  "checks": [
    {
      "id": "artifact_exists",
      "passed": true
    }
  ]
}
```

---

# 67. Audit

The audit system records:

```text
who
what
when
where
why
decision
result
correlation
```

Example:

```text
user
workspace
task
execution
action
policy decision
approval decision
outcome
```

Audit is append-oriented.

Normal application code must not casually rewrite history.

---

# 68. Observability

Every request:

```text
request_id
trace_id
```

Every execution:

```text
task_id
execution_id
```

Every step:

```text
step_id
```

Every agent/model/tool operation:

```text
agent_run_id
model_call_id
tool_call_id
```

Metrics:

```text
task creation rate
task completion rate
task failure rate
execution duration
approval wait time
verification failures
recovery count
queue depth
worker latency
API latency
API errors
```

---

# 69. Security Logging

Never log:

```text
access tokens
passwords
API keys
credentials
provider secrets
private keys
hidden chain-of-thought
```

Safe logging:

```text
task_id
execution_id
step_id
agent_id
tool_id
event_type
status
latency
risk_class
```

---

# 70. Frontend Integration

The Electron frontend currently has a clean repository/data-access seam.

Do not rewrite the UI.

Replace:

```text
local mock repository
```

with:

```text
REST API repository
+
SSE event repository
```

Architecture:

```text
React components
       ↓
frontend repository interface
       ↓
backend API client
       ↓
FastAPI
```

This keeps the page components unaware of whether the backend is real or simulated.

---

# 71. Frontend Migration Strategy

Today:

```text
UI
 ↓
Local Repository
 ↓
Mock State
```

Next:

```text
UI
 ↓
Repository Interface
 ↓
Backend API Adapter
 ↓
FastAPI
 ↓
Mock Runtime
```

Later:

```text
UI
 ↓
Repository Interface
 ↓
FastAPI
 ↓
Real Orchestrator
 ↓
Real Agents
 ↓
Real Tools
```

The UI should remain unchanged.

---

# 72. Mock Runtime

Mandatory configuration:

```text
ORCHESTRATOR_MODE=mock
AGENT_RUNTIME_MODE=mock
TOOL_RUNTIME_MODE=mock
VERIFIER_MODE=mock
POLICY_MODE=mock
```

The mock runtime should generate realistic deterministic events.

---

# 73. Flagship Mock Scenario

Input:

```text
Create my weekly operations report
```

Simulation:

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
Step 1
 ↓
Step 2
 ↓
Step 3
 ↓
Step 4
 ↓
VERIFYING
 ↓
COMPLETE
```

A richer demo:

```text
1. Resolve approved template
2. Retrieve approved data
3. Analyze data
4. Generate report.xlsx
5. Verify report
6. Prepare email draft
7. Request approval
8. Mock-send after approval
9. Verify final state
10. Complete
```

No real external message is sent.

---

# 74. Mock Recovery Scenario

```text
Step 1 ✓
Step 2 ✓
Step 3 ✗
Step 4 pending
Step 5 pending
```

Then:

```text
RECOVERY
 ↓
RE-OBSERVE
 ↓
ALTERNATE_PATH
 ↓
Step 3 ✓
 ↓
Step 4 ✓
 ↓
Step 5 ✓
```

This allows the frontend recovery UI to be tested before real automation exists.

---

# 75. Mock Approval Scenario

```text
RUNNING
 ↓
approval.requested
 ↓
AWAITING_APPROVAL
```

User approves:

```text
approval.granted
 ↓
RUNNING
 ↓
VERIFYING
 ↓
COMPLETE
```

User rejects:

```text
approval.rejected
 ↓
BLOCKED / FAILED
```

---

# 76. Backend ↔ ML Team Contract

This is the actual integration boundary between your three-person team.

### You

Own:

```text
Task API
Execution API
Approval API
Event system
Persistence
State machine
Policy boundary
Runtime interfaces
Frontend integration
```

### ML teammate #1

Owns:

```text
specialized agents
AgentRuntime implementation
agent reasoning
agent-specific evaluation
```

### ML teammate #2

Owns:

```text
orchestrator
planning
task decomposition
agent assignment
replanning logic
```

Shared:

```text
contracts/
```

---

# 77. Contract Freeze

Freeze these types:

```text
TaskRequest
Task
Plan
PlanStep
Execution
AgentRunRequest
AgentRunResult
ToolCall
ToolResult
Observation
VerificationRequest
VerificationResult
RecoveryRequest
RecoveryDecision
Approval
Artifact
ExecutionEvent
```

This is more important than choosing a framework.

---

# 78. Contract Testing

Every ML implementation must satisfy the shared schemas.

For example:

```text
real orchestrator
        ↓
Plan schema validation
        ↓
PASS / FAIL
```

and:

```text
real agent
        ↓
AgentRunResult schema
        ↓
PASS / FAIL
```

This prevents team members from creating incompatible internal APIs.

---

# 79. Test Fixtures

Create:

```text
fixtures/
├── simple.json
├── multi_step.json
├── branching.json
├── approval.json
├── recovery.json
├── invalid_plan.json
├── impossible_request.json
└── cancellation.json
```

These become the shared integration test suite.

---

# 80. API Test Requirements

Every endpoint must test:

```text
valid request
invalid request
unauthenticated
unauthorized
wrong workspace
not found
wrong state
duplicate request
concurrent request
```

---

# 81. State-Machine Tests

At minimum:

```text
QUEUED → PLANNING       PASS
PLANNING → VALIDATING   PASS
VALIDATING → RUNNING   PASS
VALIDATING → APPROVAL  PASS
APPROVAL → RUNNING     PASS
RUNNING → VERIFYING    PASS
VERIFYING → COMPLETE   PASS

COMPLETE → RUNNING      FAIL
COMPLETE → CANCELLED    FAIL
```

---

# 82. Failure Tests

Mandatory:

```text
API restart
worker restart
duplicate POST
duplicate approval
expired approval
invalidated approval
verification failure
recovery exhaustion
cancellation during execution
queue retry
desktop reconnect
event replay
concurrent workers
```

---

# 83. Local Development

Local stack:

```text
PostgreSQL
Redis
FastAPI
Worker
```

Recommended Docker Compose:

```text
postgres
redis
```

Run backend locally:

```bash
uvicorn app.main:app --reload
```

Run workers separately.

---

# 84. Development Modes

## Mode 1 — Backend only

```text
FastAPI
+
Postgres
+
Redis
+
Mock runtime
```

## Mode 2 — Backend + Electron

```text
Electron
 ↓
FastAPI
 ↓
Mock runtime
```

## Mode 3 — Backend + real ML

```text
Electron
 ↓
FastAPI
 ↓
Real orchestrator
 ↓
Real agents
```

This progression lets the team integrate incrementally.

---

# 85. Production Environment

Future production architecture:

```text
                Load Balancer
                     ↓
              API Workers
                     ↓
              PostgreSQL
                     ↓
                  Queue
              ↙          ↘
       Planning Workers   Execution Workers
              ↓               ↓
         Orchestrator      Agents/Tools
                     ↓
                 Verifier
                     ↓
               Object Store
```

Plus:

```text
secret manager
observability
backup
restore
monitoring
```

---

# 86. Production Readiness

The project's requirements already define production readiness around:

```text
persistent workflow state
bounded retries
recovery/replan
no silent success
authentication
tenant isolation
RBAC
secret isolation
default-deny tools
audit logging
```



The backend must establish the infrastructure needed for those properties even before real tools exist.

---

# 87. Critical Architectural Invariants

These should be written into the codebase as explicit engineering rules.

```text
1. No LLM has unrestricted side-effect authority.

2. Material actions require deterministic validation.

3. Material steps require verification.

4. Approval binds to exact action/plan identity.

5. Authorization is independent from retrieval relevance.

6. Desktop is a client of backend.

7. Provider secrets remain outside renderer.

8. Execution state is durable.

9. Recovery is bounded.

10. Every execution remains auditable.
```

These invariants are explicitly established in the existing project vision.

---

# 88. Implementation Order

This is the exact order I recommend for you now.

## Phase 1 — Contracts

Build:

```text
domain enums
Pydantic schemas
JSON schemas
state machine
event schemas
```

No database yet.

---

## Phase 2 — Database

Build:

```text
PostgreSQL
SQLAlchemy models
Alembic migrations
repositories
```

---

## Phase 3 — Task API

Implement:

```text
POST /tasks
GET /tasks
GET /tasks/{id}
POST /tasks/{id}/cancel
```

---

## Phase 4 — Execution API

Implement:

```text
GET /executions
GET /executions/{id}
POST /executions/{id}/pause
POST /executions/{id}/resume
POST /executions/{id}/cancel
```

---

## Phase 5 — Approval

Implement:

```text
GET /approvals
GET /approvals/{id}
POST /approve
POST /reject
```

---

## Phase 6 — Event System

Implement:

```text
persistent events
event sequences
SSE
reconnect
event replay
```

---

## Phase 7 — Mock Runtime

Implement:

```text
MockOrchestrator
MockAgentRuntime
MockToolRuntime
MockVerifier
MockPolicyEngine
MockRecoveryManager
```

---

## Phase 8 — Frontend Integration

Replace the frontend mock repository with:

```text
BackendApiRepository
```

and connect:

```text
REST
+
SSE
```

---

## Phase 9 — Full Synthetic Execution

The entire system should perform:

```text
Create task
 ↓
Plan
 ↓
Validate
 ↓
Approval
 ↓
Approve
 ↓
Execute
 ↓
Verify
 ↓
Artifact
 ↓
Complete
```

without real AI.

---

## Phase 10 — ML Integration

Replace:

```text
MockOrchestrator
```

with:

```text
RealOrchestrator
```

Replace:

```text
MockAgentRuntime
```

with:

```text
RealAgentRuntime
```

No API redesign.

---

# 89. First Vertical Slice

This is the most important development milestone.

User enters:

```text
Create my weekly operations report
```

Then:

```text
Electron
   ↓
POST /api/v1/tasks
   ↓
FastAPI
   ↓
Task persisted
   ↓
Execution created
   ↓
Mock orchestrator
   ↓
Plan persisted
   ↓
Plan validated
   ↓
Approval requested
   ↓
SSE
   ↓
Electron shows approval
   ↓
User approves
   ↓
Mock agent
   ↓
Mock tools
   ↓
Mock verifier
   ↓
Artifact
   ↓
COMPLETE
   ↓
SSE
   ↓
Electron shows verified result
```

If this works, your architecture is proven.

---

# 90. Definition of Done

The backend foundation is complete when:

### API

```text
Task creation        ✓
Task retrieval        ✓
Task cancellation     ✓
Execution retrieval   ✓
Approval              ✓
Artifact metadata     ✓
Event streaming       ✓
```

### Persistence

```text
Restart-safe          ✓
Migrations            ✓
Transactions           ✓
Idempotency            ✓
```

### Runtime

```text
Mock orchestrator     ✓
Mock agents            ✓
Mock tools             ✓
Mock verifier          ✓
Mock recovery          ✓
Mock approval          ✓
```

### Security

```text
Authentication        ✓
Workspace isolation   ✓
RBAC                   ✓
Policy boundary       ✓
Approval enforcement  ✓
Audit                  ✓
```

### Integration

```text
Electron → API         ✓
API → worker           ✓
worker → mock runtime  ✓
runtime → events       ✓
events → Electron      ✓
```

### Reliability

```text
Worker restart         ✓
API restart            ✓
Duplicate request      ✓
Reconnect               ✓
Recovery               ✓
Cancellation           ✓
```

---

# 91. What You Should Build First Tomorrow

Do **not** start with:

```text
real agents
real LLM
real browser automation
real email
real RAG
```

Start here:

```text
backend/
contracts/
```

Then implement, in order:

```text
Task schema
Plan schema
PlanStep schema
Execution schema
Approval schema
ExecutionEvent schema
Verification schema
```

Then:

```text
state machine
```

Then:

```text
PostgreSQL
```

Then:

```text
POST /api/v1/tasks
```

Then:

```text
GET /api/v1/tasks/{id}
```

Then the first mock planner.

---

# 92. The Most Important Team Decision

Your three-person architecture should now be:

```text
                 ┌─────────────────────┐
                 │     Electron        │
                 │       YOU           │
                 └──────────┬──────────┘
                            │
                         API/SSE
                            │
                            ▼
                 ┌─────────────────────┐
                 │   BACKEND CONTROL   │
                 │       YOU           │
                 └──────────┬──────────┘
                            │
                     ┌──────┴──────┐
                     │             │
                     ▼             ▼
             ┌──────────────┐ ┌──────────────┐
             │ ORCHESTRATOR │ │ AGENT RUNTIME│
             │   ML #2      │ │    ML #1     │
             └──────────────┘ └──────────────┘
```

And the shared boundary is:

```text
contracts/
```

That is the key.

---

# 93. Final Principle

The backend should enforce this model:

```text
                 USER
                  │
                  ▼
                GOAL
                  │
                  ▼
             ORCHESTRATOR
                  │
                  ▼
                 PLAN
                  │
                  ▼
            CONTROL PLANE
       ┌──────────┼──────────┐
       │          │          │
     POLICY    APPROVAL    STATE
       │          │          │
       └──────────┼──────────┘
                  ▼
             AGENT RUNTIME
                  │
                  ▼
             TOOL RUNTIME
                  │
                  ▼
             OBSERVATION
                  │
                  ▼
             VERIFICATION
                  │
          ┌───────┴───────┐
          │               │
        SUCCESS         FAILURE
          │               │
          ▼               ▼
       COMPLETE        RECOVERY
                          │
                          ▼
                       REPLAN
```

**The intelligence decides what should happen.**

**The backend controls whether, when, and under what authority it happens.**

**The execution runtime performs it.**

**Verification determines whether it actually worked.**

That separation is what prevents AutoFlow from collapsing into “an LLM with a bunch of API calls.”

---

# 94. Backend PRD Exit Condition

The backend phase is successful when:

> **Everything that can currently run in the AI/ML test harness can be triggered, observed, controlled, approved, persisted, and audited through stable APIs.**

That is also the project's stated backend-phase exit condition.

At that point, your Electron app becomes the **face**, the backend becomes the **control plane**, your ML team's orchestrator becomes the **brain for planning**, the specialized agents provide **capability**, the tools provide the **hands**, and verification provides the **truth mechanism**.