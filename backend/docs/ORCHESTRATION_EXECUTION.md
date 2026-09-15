# AutoFlow AI Backend — Orchestration and Execution

## 1. Objective

This document defines how the backend turns AI/ML decisions into durable work.

The AI/ML subsystem already establishes the central distinction: the planner answers the whole-job question, the execution agent decides the next safe operation, tool calling selects an approved function, deterministic runtime performs it, and verification decides whether the outcome is real. fileciteturn4file2L371-L450

The backend supplies persistence, concurrency, approval, scheduling, workers, reconciliation and API control around that runtime.

---

## 2. Canonical Execution Pipeline

```text
REQUEST
 ↓
TASK CREATED
 ↓
CONTEXT BUILT
 ↓
PLAN GENERATED
 ↓
PLAN VALIDATED
 ↓
PLAN VERSION FROZEN
 ↓
APPROVAL ANALYSIS
 ↓
QUEUE
 ↓
EXECUTION WORKER
 ↓
SELECT READY STEP
 ↓
AGENT RUN
 ↓
MODEL ROUTE
 ↓
TOOL PROPOSAL
 ↓
SCHEMA + POLICY + PERMISSION
 ↓
TOOL RUNTIME
 ↓
OBSERVATION
 ↓
VERIFICATION
 ├── PASS → NEXT STEP
 └── FAIL → RECOVERY
                  ├ retry
                  ├ re-observe
                  ├ re-resolve
                  ├ alternate tool
                  ├ bounded replan
                  └ human
 ↓
FINAL VERIFICATION
 ↓
ARTIFACTS
 ↓
RESULT
 ↓
AUDIT
 ↓
WORKFLOW MEMORY
```

---

## 3. Execution State Machine

States:

```text
QUEUED
PLANNING
VALIDATING
AWAITING_APPROVAL
RUNNING
VERIFYING
RECOVERY
PAUSED
COMPLETE
FAILED
CANCELLED
EXPIRED
BLOCKED
```

Rules:

- only authorized transitions are allowed;
- every transition is persisted;
- every transition emits an event;
- workers re-read current state before new side effects.

---

## 4. Task Graph Representation

Each step contains:

```text
step_id
objective
agent_id
dependencies
preconditions
expected_state
inputs
outputs
tool_capabilities
verification
risk_class
approval_requirement
timeout
retry_budget
replan_budget
```

Ready-step calculation:

```text
step is READY when:
all dependencies COMPLETE
AND preconditions satisfied
AND execution RUNNING
AND approval constraints satisfied
```

---

## 5. Parallel Execution

Independent steps can run concurrently.

```text
            +→ research customer
            |
PLAN ───────+→ retrieve policy
            |
            +→ inspect source file
                         |
                         v
                     synthesis
```

Concurrency limits must exist at:

```text
organization
workspace
execution
agent
provider
connector
worker pool
```

---

## 6. Worker Loop

Pseudo-flow:

```python
while True:
    job = queue.receive()
    if not job:
        continue

    lease = execution_store.acquire_lease(job.execution_id)
    if not lease:
        continue

    try:
        execution = store.load(job.execution_id)
        if execution.is_terminal_or_paused():
            continue

        step = scheduler.select_ready_step(execution)
        if step is None:
            reconciler.finalize_or_wait(execution)
            continue

        runner.run_step(execution, step)
    finally:
        lease.release_or_expire()
```

Real implementation must also support heartbeats, cancellation and process termination safely.

---

## 7. Lease Model

Workers should lease work for a bounded period.

```text
lease acquired
 ↓
heartbeat
 ↓
side-effect execution
 ↓
result persisted
 ↓
lease released
```

A worker crash leaves the lease to expire.

Reconciliation decides whether to retry.

---

## 8. Step Execution Transaction

A step should be persisted as running before a side effect.

```text
transaction:
  step.status = RUNNING
  attempt += 1
commit
```

Then:

```text
execute external tool
```

Then:

```text
transaction:
  tool result
  observation
  verification
  step status
  events
commit
```

Because external effects are outside the database transaction, the tool needs idempotency or reconciliation support.

---

## 9. Tool Proposal Validation

The model output is never executed directly.

```text
model output
 ↓
JSON/schema validation
 ↓
tool exists
 ↓
agent may use tool
 ↓
workspace allows tool
 ↓
permission allows tool
 ↓
risk evaluation
 ↓
approval check
 ↓
execution
```

The AI/ML runtime explicitly requires structured tool calls and deterministic side-effect execution. fileciteturn4file1L193-L215

---

## 10. Context Reconstruction

Every worker call must reconstruct the current context from durable state.

```text
task
+
plan version
+
current step
+
previous observations
+
recovery history
+
retrieved knowledge
+
permissions
+
available tools
+
remaining budgets
```

Do not depend on a long-lived Python worker object as the single source of truth.

---

## 11. Observation

An observation is the bridge between an attempted action and reality.

Examples:

```json
{
  "type": "file",
  "path": "...",
  "exists": true,
  "size": 18291,
  "hash": "sha256:..."
}
```

```json
{
  "type": "ui",
  "application": "Word",
  "window": "Document 1",
  "target": {"role": "button", "name": "Save"},
  "state_hash": "..."
}
```

---

## 12. Verification

Verification examples:

```text
file exists
file opens
expected content present
totals reconcile
email draft recipient correct
send state observable
browser page contains expected record
UI reached expected state
```

A tool response of `success: true` is not sufficient when the business outcome needs stronger evidence. The AI/ML execution runtime makes this explicit. fileciteturn4file3L760-L783

---

## 13. Recovery

Recovery ladder:

```text
FAILURE
 ↓
TRANSIENT?
 ├ yes → bounded retry
 └ no
     ↓
re-observe
     ↓
re-resolve target
     ↓
alternate safe method
     ↓
bounded replan
     ↓
human escalation
```

Recovery budgets:

```text
max attempts
max minutes
max model calls
max replans
max external cost
```

This mirrors the AI/ML recovery strategy. fileciteturn4file3L785-L810

---

## 14. Replanning

Only the affected suffix should be regenerated when possible.

```text
step 1 ✓
step 2 ✓
step 3 ✗
step 4 pending
step 5 pending

replan:
step 3 → alternate path → step 4 → step 5
```

The backend persists each new plan version and references the parent version.

---

## 15. Approval Pause

When the worker reaches a high-risk action:

```text
worker
 ↓
risk evaluation
 ↓
create approval
 ↓
transaction:
  approval record
  step = AWAITING_APPROVAL
  execution = AWAITING_APPROVAL
  outbox event
 ↓
commit
 ↓
worker exits
```

Approval response:

```text
approve
 ↓
validate action_hash
 ↓
validate expiry
 ↓
validate still-current plan
 ↓
RUNNING
 ↓
requeue worker
```

---

## 16. Pause / Resume

Pause means no new side effects begin.

A running external operation may complete if it cannot be safely interrupted; its result must still be verified.

Resume creates a new worker lease rather than mutating an old worker process.

---

## 17. Cancellation

Cancellation is persisted first.

```text
POST /cancel
 ↓
execution = CANCEL_REQUESTED/CANCELLED
 ↓
workers observe flag
 ↓
no new side effect
 ↓
current interruptible tools stop
 ↓
state finalization
```

Never rely exclusively on the HTTP caller remaining connected.

---

## 18. Idempotency

Use:

```text
execution_id + step_id + attempt_id
```

Where an external connector supports idempotency keys, pass a stable key.

Example email:

```text
autoflow:exec_123:step_7:send
```

Retry path:

```text
check whether already sent
 ↓
if yes → verify
if no → send
```

---

## 19. End-to-End Document + Email Workflow

User says:

> “Edit this Word file, save the same file, create an email to the sender, attach the edited document, and send it after I approve.”

Backend flow:

```text
1. Create task
2. Resolve workspace/user
3. Inspect attachment metadata
4. Retrieve relevant document-editing guidance
5. Planner creates graph
6. Validate plan
7. Document agent reads file
8. Document tool applies edits
9. Save same file
10. Verify file hash/content
11. Communication agent resolves sender
12. Create email draft
13. Attach verified artifact
14. Verify draft recipients/attachment
15. Approval required
16. Persist approval
17. WAIT
18. User approves
19. Revalidate action hash
20. Send email
21. Verify external send state
22. Final verification
23. Return file + send evidence
24. Save reusable semantic workflow if policy permits
```

This is the minimum standard for “one prompt does the work.”

---

## 20. Browser Workflow

```text
prompt
 ↓
planner
 ↓
login/session resolution
 ↓
browser navigation
 ↓
semantic target resolution
 ↓
action
 ↓
page observation
 ↓
verification
 ↓
next step
```

Browser automation should use structured page semantics wherever possible, with visual grounding as fallback.

---

## 21. Desktop Workflow

```text
prompt
 ↓
computer-agent
 ↓
UI Automation
 ↓
application adapter
 ↓
visual grounding if needed
 ↓
execute
 ↓
capture observation
 ↓
verify
```

The workflow representation remains semantic rather than coordinate-based.

---

## 22. Automation Workflow

For a scheduled workflow:

```text
scheduler tick
 ↓
automation definition
 ↓
create task
 ↓
normal plan/execution path
 ↓
approval if required
 ↓
complete
```

Automation should not bypass policy simply because a schedule triggered it.

---

## 23. Concurrency Controls

An execution scheduler should support:

```text
max concurrent executions/workspace
max concurrent steps/execution
max concurrent model calls
max concurrent connector calls
max browser sessions
```

Fairness should prevent one organization from monopolizing workers.

---

## 24. Reconciliation Jobs

Periodic reconciler checks:

```text
expired worker leases
stuck approvals
orphaned executions
missing event deliveries
artifact verification pending
provider call records without completion
scheduled jobs missed due to outage
```

Reconciliation must be deterministic and idempotent.

---

## 25. Execution Events

Minimum:

```text
task.created
execution.queued
plan.created
plan.validated
execution.started
step.started
agent.started
model.call.completed
tool.started
tool.completed
observation.created
verification.passed
verification.failed
recovery.started
approval.requested
approval.granted
step.completed
execution.completed
execution.failed
```

---

## 26. Execution Metrics

Per execution:

```text
planning_latency
model_latency
tool_latency
queue_wait
approval_wait
step_count
tool_call_count
verification_pass_rate
recovery_count
replan_count
total_duration
estimated_cost
```

---

## 27. Execution Definition of Done

```text
[ ] workflow survives worker crash
[ ] workflow survives API restart
[ ] approval pause/resume works
[ ] cancel is persistent
[ ] retries do not duplicate supported external effects
[ ] verification controls completion
[ ] recovery is bounded
[ ] parallel tasks are isolated
[ ] event history reconstructs execution
[ ] final artifacts are linked
[ ] manual and scheduled workflows share engine
```
