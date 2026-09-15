# AutoFlow AI Backend

The backend is the control plane for AutoFlow AI. It makes the AI/ML execution engine persistent, secure, multi-tenant, observable and accessible through APIs.

## Documentation Order

```text
1. BACKEND_PRD.md
2. BACKEND_ARCHITECTURE.md
3. API.md
4. AUTH_TENANCY_SECURITY.md
5. ORCHESTRATION_EXECUTION.md
6. INTEGRATIONS_MODELS_STORAGE.md
7. BACKEND_TASKS.md
```

## Core Flow

```text
CLIENT
 ↓
AUTH / TENANT / WORKSPACE
 ↓
TASK
 ↓
PLAN
 ↓
VALIDATE
 ↓
APPROVAL
 ↓
EXECUTION WORKER
 ↓
MODEL / AGENT
 ↓
TOOL / CONNECTOR
 ↓
OBSERVE
 ↓
VERIFY
 ↓
RECOVER / REPLAN
 ↓
ARTIFACT / RESULT
 ↓
AUDIT / WORKFLOW MEMORY
```

## Source of Truth Rules

- PostgreSQL is authoritative for backend domain state.
- ChromaDB is a semantic index, not an authorization system.
- Object storage holds artifact bytes.
- Queue systems move work; they do not become the source of truth.
- The AI/ML subsystem owns model/agent reasoning contracts.
- The backend owns identity, tenancy, policy, persistence, execution control, approvals, API contracts and observability.
- Electron is a client of the backend.

## Local Development Direction

Start with a single deployable FastAPI backend and local dependencies, then split services only when measurement shows the need.

Suggested local components:

```text
backend
PostgreSQL
Redis/queue
ChromaDB
local object-store emulator
optional self-hosted/open-weight model server
```

## Critical Invariant

```text
NO LLM → DIRECT SIDE EFFECT

LLM
 ↓
STRUCTURED PROPOSAL
 ↓
SCHEMA
 ↓
POLICY
 ↓
PERMISSION
 ↓
DETERMINISTIC RUNTIME
 ↓
OBSERVATION
 ↓
VERIFICATION
```

## First Backend Milestone

The first real backend demo is not a login screen. It is an API-driven task that completes a durable end-to-end workflow and leaves a verifiable audit trail.

```text
POST /api/v1/tasks
 ↓
plan
 ↓
validate
 ↓
execute
 ↓
approve when required
 ↓
verify
 ↓
artifact
 ↓
audit
```
