# AutoFlow AI — System Architecture

## 1. System Definition

AutoFlow is a distributed agentic execution system with four major planes:

```text
HUMAN PLANE
Desktop / approvals / task composer

CONTROL PLANE
Auth / tenancy / orchestration / state / policy / audit

INTELLIGENCE PLANE
Agents / model gateway / RAG / planning / recovery reasoning

EXECUTION PLANE
APIs / files / browser / desktop / code sandbox / artifacts
```

## 2. End-to-End Flow

```text
User Login
 ↓
Organization + Workspace Resolution
 ↓
User Prompt + Attachments
 ↓
Normalization
 ↓
Intent / Capability / Risk Analysis
 ↓
Authorized Knowledge Retrieval
 ↓
Task Decomposition
 ↓
Agent Assignment
 ↓
Model Routing
 ↓
Structured Plan
 ↓
Deterministic Validation
 ↓
Approval Detection
 ↓
Human Approval if required
 ↓
Execution Loop
 ↓
Observation
 ↓
Verification
 ↓
Recovery / Replan if needed
 ↓
Artifacts / External Outcome
 ↓
Final Verification
 ↓
Audit
 ↓
Verified Workflow Memory
```

## 3. Service Boundaries

### Identity
Authenticates users and emits identity/role/workspace context.

### Orchestrator
Owns task graph, state transitions, scheduling and dependencies.

### Model Gateway
Owns all model/provider interaction.

### Knowledge Service
Owns indexing and authorization-aware retrieval.

### Tool Registry
Defines what tools exist and under what permissions they may run.

### Execution Runtime
Performs deterministic side effects.

### Verification
Checks postconditions.

### Recovery
Coordinates bounded retries and replanning.

### Artifact Service
Creates, stores and validates deliverables.

### Audit/Observability
Creates the durable operational trail.

## 4. Request Contract

Every task request should have an identity and workspace boundary before any model planning starts.

```text
TaskRequest
├── task_id
├── actor
├── organization_id
├── workspace_id
├── goal
├── attachments
├── constraints
├── client_metadata
└── policy_profile
```

## 5. Execution Isolation

Every execution receives:

```text
execution_id
workspace scope
permission snapshot
policy snapshot
context namespace
tool allowlist
artifact namespace
budget
```

## 6. Event-Driven Runtime

Long-running tasks should use persistent events and worker queues rather than blocking one API request.

```text
POST /tasks
   ↓
Task persisted
   ↓
Queue
   ↓
Worker
   ↓
Execution events
   ↓
WebSocket/SSE
   ↓
Desktop
```

## 7. Data Stores

```text
PostgreSQL
  authoritative metadata/state

Vector DB
  semantic knowledge retrieval

Object storage
  artifacts / large files

Optional graph store
  workflow relationships

Redis / queue
  transient coordination / queueing
```

## 8. Security Boundary

```text
Client input
   ↓
Auth
   ↓
Authorization
   ↓
Policy
   ↓
Model
   ↓
Structured action
   ↓
Tool validation
   ↓
Execution
```

No client-side model decision is authoritative.

## 9. Extensibility

New capability is introduced through interfaces:

```text
new model provider
new agent profile
new tool
new connector
new verifier
new application adapter
new workflow type
```

Core orchestration remains stable.
