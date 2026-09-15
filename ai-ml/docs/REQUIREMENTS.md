# AutoFlow AI — AI/ML Requirements

**Status:** Engineering baseline
**Owner:** AI/ML + Platform
**Source of truth:** Product PRD and AI/ML architecture

## 1. Product-level requirement

AutoFlow AI must accept a natural-language objective and transform it into a controlled, observable and verifiable workflow. The AI/ML subsystem must operate independently of the desktop UI.

## 2. Functional requirements

### FR-01 — Task understanding

Input:
- user goal;
- files/attachments;
- workspace/tenant context;
- explicit constraints;
- deadline and output requirements when provided.

Output must be a normalized task request containing intent, entities, constraints, required capabilities, risk hints and missing information.

### FR-02 — Context grounding

The runtime must be able to consume authorized knowledge, current task state, tool availability and prior verified workflow memory. Retrieved context must preserve provenance and access scope.

### FR-03 — Planning

The planner must generate a structured DAG/task graph containing:
- step ID;
- objective;
- assigned agent;
- dependencies;
- inputs;
- preconditions;
- expected state;
- tool capabilities;
- verification requirements;
- risk class;
- approval requirement;
- timeout/budget.

### FR-04 — Specialist agents

The system must support extensible specialist agent profiles without changing the core orchestration protocol.

Initial families:
1. Research Agent
2. Document Agent
3. Spreadsheet/Data Agent
4. Presentation Agent
5. Coding Agent
6. Communication Agent
7. Browser Automation Agent
8. Computer Automation Agent
9. QA/Verification Agent

The system must permit additional agents later.

### FR-05 — Model routing

Agents request capabilities, not hard-coded provider calls. The gateway must select an eligible model based on capability, context, risk, latency, reliability, policy and cost constraints.

### FR-06 — Structured generation

Planner, executor and tool-calling outputs must be machine-validatable. Invalid structured output must fail safely and trigger bounded repair/retry.

### FR-07 — Tool selection

A tool-calling controller may map a semantic operation to one approved function and arguments. It must not invent tools outside the allowed tool registry.

### FR-08 — Deterministic execution

Side effects must be performed by deterministic tool runtimes. Examples include browser automation, desktop UI automation, HTTP integrations, files, documents and sandboxed code.

### FR-09 — Observation

Every consequential step must emit an observation that captures the actual post-action state needed for verification.

### FR-10 — Verification

Material steps cannot become complete on tool-response success alone. Verification must evaluate postconditions and generate evidence.

### FR-11 — Recovery

Failures must follow bounded recovery policies: retry, re-observe, re-resolve, alternate tool/path, bounded replan, human escalation.

### FR-12 — Human approval

High-risk or externally visible actions must be able to pause execution and resume only after an approved decision bound to the relevant action/plan version.

### FR-13 — Persistent execution

Execution state must survive process restart and reconnect. State must be recoverable from persisted events/checkpoints.

### FR-14 — Concurrent workflows

Multiple tasks may execute simultaneously. Each execution must isolate context, variables, permissions, tool scope, state and artifacts.

### FR-15 — Workflow memory

Only sufficiently verified executions should be eligible for reusable workflow memory. Raw coordinates must never be the canonical workflow representation.

## 3. Model requirements

### MR-01 — Provider abstraction

All models must be accessed through a provider-neutral interface.

### MR-02 — Capability metadata

Every registered model must declare:
- modalities;
- context limits;
- structured-output capability;
- tool-calling capability;
- vision capability;
- coding/reasoning capability;
- embedding capability when relevant;
- latency characteristics;
- cost information when known;
- deployment type;
- health status.

### MR-03 — Fallback

Provider/model failure must trigger a controlled fallback only when the fallback remains policy-compatible with the task.

### MR-04 — Secret isolation

API credentials must never be exposed to the Electron renderer, model prompts, logs or agent-visible context unless an explicitly designed connector requires a secure scoped token.

### MR-05 — Testability

Every registered production model must have automated tests for structured output, tool calling where supported, timeout behavior and provider failure behavior.

## 4. Computer-use requirements

### CU-01 — Semantic targets

Computer actions should be represented semantically, e.g.:

```json
{"role":"button","name":"Save","confidence":0.96}
```

not as canonical fixed coordinates.

### CU-02 — Resolution hierarchy

```text
Connector/API
→ Accessibility/UI Automation
→ DOM/semantic metadata
→ Application adapter
→ Visual grounding
→ Human escalation
```

### CU-03 — Grounding evidence

Visual grounding must produce confidence and target metadata. Low-confidence target resolution must not silently execute a dangerous action.

## 5. Safety requirements

- deny-by-default tool permissions;
- schema validation on all model-generated actions;
- risk classification before execution;
- approval for configured high-risk operations;
- bounded model/tool loops;
- persistent cancellation;
- idempotency where practical;
- prompt-injection resistance through context separation;
- audit-ready execution events.

## 6. Non-functional requirements

### Performance

- non-blocking async model calls;
- streaming support where provider permits;
- configurable timeouts;
- bounded queue depth;
- predictable token/tool budgets.

### Reliability

- no infinite autonomous loops;
- no silent transition to COMPLETE after verification failure;
- deterministic state transitions;
- idempotent retry strategy for supported tools.

### Observability

Trace at minimum:

```text
task → execution → step → agent run → model call → tool call → observation → verification
```

### Security

- least privilege;
- tenant/workspace isolation;
- secret isolation;
- secure connector credentials;
- explicit egress policy at the platform layer.

### Maintainability

Model providers, agents, tools and schemas must be independently replaceable.

## 7. Acceptance criteria

The AI/ML subsystem is accepted only when all of the following are true:

```text
[ ] One prompt becomes a valid task graph.
[ ] The graph passes deterministic validation.
[ ] A real execution can proceed without Electron.
[ ] Tool calls are schema-valid and permission-checked.
[ ] Verification is mandatory for material steps.
[ ] Recovery is bounded and measurable.
[ ] Approval pause/resume works.
[ ] A failed provider can be handled without corrupting execution state.
[ ] Multiple tasks remain isolated.
[ ] Golden tasks run automatically in CI.
[ ] Adversarial and failure cases are included.
[ ] Metrics are recorded for each release candidate.
```
