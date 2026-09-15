# AutoFlow AI Backend — Implementation Tasks and Test Gates

## Phase 0 — Backend Foundation

- [ ] Create FastAPI application shell.
- [ ] Add configuration loader.
- [ ] Add environment validation.
- [ ] Add structured logging.
- [ ] Add request/trace IDs.
- [ ] Add health/readiness endpoints.
- [ ] Add dependency container.
- [ ] Add database migration framework.
- [ ] Add test settings.

**Exit test:** backend boots from a clean environment and `/health`, `/ready` behave correctly.

---

## Phase 1 — PostgreSQL and Domain Schemas

- [ ] organizations
- [ ] users
- [ ] memberships
- [ ] workspaces
- [ ] roles
- [ ] permissions
- [ ] tasks
- [ ] plans
- [ ] plan_versions
- [ ] executions
- [ ] execution_steps
- [ ] execution_events
- [ ] approvals
- [ ] agents
- [ ] models
- [ ] tools
- [ ] connectors
- [ ] knowledge sources
- [ ] workflow memories
- [ ] artifacts
- [ ] automations
- [ ] audit events

**Tests:** migrations from empty DB; rollback strategy; foreign-key constraints; tenant scoping.

---

## Phase 2 — Authentication and Tenancy

- [ ] login/session implementation
- [ ] token verification
- [ ] `/me`
- [ ] organization membership
- [ ] workspace membership
- [ ] RBAC middleware
- [ ] permission dependency helpers
- [ ] tenant query helpers
- [ ] audit principal resolution

**Tests:** cross-tenant access; revoked user; wrong workspace; expired token; insufficient role.

---

## Phase 3 — Task API

- [ ] create task
- [ ] get task
- [ ] list tasks
- [ ] attachment linking
- [ ] task pause
- [ ] task resume
- [ ] task cancel
- [ ] idempotent task creation

**Tests:** duplicate request; malformed prompt; missing workspace; unauthorized attachment; cancellation persistence.

---

## Phase 4 — AI/ML Bridge

- [ ] model provider interface
- [ ] provider registry
- [ ] self-hosted/OpenAI-compatible adapter
- [ ] cloud adapter
- [ ] model health checks
- [ ] planner bridge
- [ ] structured response validation
- [ ] request/response telemetry

**Tests:** model timeout; invalid JSON; provider 500; fallback; model unavailable; secret non-disclosure.

---

## Phase 5 — Plan and Validation

- [ ] plan persistence
- [ ] plan versioning
- [ ] canonical hashing
- [ ] schema validation
- [ ] policy validation
- [ ] approval detection
- [ ] plan retrieval API

**Tests:** malformed plan; duplicate step ID; cyclic graph; unknown agent; unknown tool; approval mutation.

---

## Phase 6 — Execution Workers

- [ ] queue abstraction
- [ ] worker process
- [ ] execution lease
- [ ] heartbeat
- [ ] ready-step scheduler
- [ ] step state persistence
- [ ] cancellation checks
- [ ] recovery hooks

**Tests:** worker kill; lease expiry; duplicate job delivery; stale worker; concurrent execution.

---

## Phase 7 — Approval System

- [ ] approval entity
- [ ] risk policy evaluator
- [ ] approval hash binding
- [ ] approve
- [ ] reject
- [ ] expire
- [ ] revalidation

**Tests:** approval replay; action mutation; expiry; unauthorized approver; duplicate approval.

---

## Phase 8 — Event Streaming

- [ ] normalized event schema
- [ ] outbox table
- [ ] dispatcher
- [ ] SSE or WebSocket
- [ ] replay from event ID
- [ ] reconnect support

**Tests:** client reconnect; event ordering; duplicate events; worker crash during event publish.

---

## Phase 9 — Tool/Connector Gateway

- [ ] tool registry
- [ ] permission checks
- [ ] connector registry
- [ ] connector credential storage
- [ ] execution gateway
- [ ] observation persistence
- [ ] verification callback

**Tests:** tool not registered; wrong permission; invalid arguments; connector timeout; duplicate side effect.

---

## Phase 10 — Knowledge and ChromaDB

- [ ] source registration
- [ ] ingestion pipeline
- [ ] parsing
- [ ] chunking
- [ ] embeddings
- [ ] ChromaDB collection manager
- [ ] ACL metadata
- [ ] semantic search endpoint
- [ ] reranking hook
- [ ] provenance model

**Tests:** unauthorized chunk excluded; deleted source disappears; index rebuild; duplicate ingestion; versioning.

---

## Phase 11 — Workflow Memory

- [ ] execution trace normalizer
- [ ] semantic action representation
- [ ] workflow candidate creation
- [ ] policy filter
- [ ] approval/trust criteria
- [ ] workflow versioning
- [ ] vector indexing
- [ ] retrieval

**Tests:** failed execution never becomes canonical; coordinate-only trace rejected; version update; provenance preserved.

---

## Phase 12 — Artifacts

- [ ] upload service
- [ ] object storage adapter
- [ ] metadata
- [ ] content hash
- [ ] artifact download
- [ ] verification metadata
- [ ] retention policy

**Tests:** corrupt upload; path traversal; hash mismatch; unauthorized download.

---

## Phase 13 — Automations

- [ ] automation CRUD
- [ ] scheduler
- [ ] timezone handling
- [ ] enable/disable
- [ ] manual run
- [ ] concurrency policy
- [ ] missed-run reconciliation

**Tests:** duplicate scheduled run; restart during schedule; daylight-saving transition where relevant; overlapping run policy.

---

## Phase 14 — Browser/Desktop Backend Gateway

- [ ] browser session resource
- [ ] desktop device resource
- [ ] worker registration
- [ ] command channel
- [ ] observation channel
- [ ] verification integration
- [ ] session cleanup

**Tests:** worker disconnect; stale command; wrong workspace; screenshot privacy; action replay.

---

## Phase 15 — Observability

- [ ] traces
- [ ] metrics
- [ ] audit views
- [ ] model call telemetry
- [ ] tool latency
- [ ] queue latency
- [ ] approval wait time
- [ ] execution outcome metrics

Required trace:

```text
task
→ execution
→ step
→ agent run
→ model call
→ tool call
→ observation
→ verification
```

---

## Phase 16 — End-to-End Golden Tasks

### Golden 1 — Create document

```text
POST task
→ planner
→ document agent
→ create DOCX
→ verify
→ return artifact
```

### Golden 2 — Edit existing document

```text
find existing file
→ inspect
→ apply edits
→ save same logical file
→ reopen
→ verify requested change
```

### Golden 3 — Email with approval

```text
find sender
→ create draft
→ attach document
→ verify draft
→ approval
→ send
→ verify
```

### Golden 4 — Browser task

```text
navigate
→ find record
→ download
→ verify
```

### Golden 5 — Desktop task

```text
open app
→ inspect UI
→ locate semantic control
→ act
→ verify state
```

### Golden 6 — Recovery

```text
first action fails
→ re-observe
→ alternate path
→ verify
```

---

## Phase 17 — Chaos Tests

Run with induced failures:

```text
API restart
worker kill
queue delay
provider timeout
provider 500
malformed model output
Chroma outage
Postgres reconnect
connector 429
browser crash
UI layout change
artifact corruption
approval expiry
```

Expected behavior must be defined for each scenario.

---

## Phase 18 — Security Tests

- [ ] cross-tenant access
- [ ] cross-workspace retrieval
- [ ] prompt injection
- [ ] confused deputy
- [ ] forbidden tool
- [ ] secret leakage
- [ ] SSRF
- [ ] path traversal
- [ ] approval bypass
- [ ] sandbox boundary

---

## Phase 19 — Load and Endurance

Measure:

```text
10 concurrent tasks
50 concurrent tasks
100 concurrent lightweight tasks
parallel model calls
parallel approvals
long-running browser executions
large artifact workflows
24h endurance
worker churn
```

Targets should be measured per deployment profile rather than invented universally.

---

## Phase 20 — Release Checklist

```text
[ ] migrations pass
[ ] API contract tests pass
[ ] auth tests pass
[ ] tenant isolation pass
[ ] provider tests pass
[ ] Chroma tests pass
[ ] execution tests pass
[ ] approval tests pass
[ ] artifact tests pass
[ ] event stream tests pass
[ ] security suite pass
[ ] chaos suite pass
[ ] golden suite pass
[ ] load test report generated
[ ] rollback procedure tested
[ ] deployment health checks pass
[ ] desktop can connect to stable APIs
```
