# AutoFlow AI — Agent Brain and Orchestration

## 1. Architecture

The agent brain is not a single prompt. It is a coordinated runtime made from specialized decision layers.

```text
USER GOAL
   ↓
INTENT NORMALIZER
   ↓
CONTEXT / MEMORY RETRIEVAL
   ↓
PLANNER
   ↓
TASK GRAPH
   ↓
AGENT ASSIGNMENT
   ↓
MODEL ROUTING
   ↓
EXECUTION AGENT
   ↓
TOOL CALLING
   ↓
OBSERVE
   ↓
VERIFY
   ├── success → next step
   └── failure → recovery/replan
```

## 2. Initial agent system

### 2.1 Planner Agent

Question: **What is the whole job?**

Responsibilities:
- understand outcome;
- decompose work;
- identify dependencies;
- predict required capabilities;
- define expected states;
- define verification;
- mark approval boundaries.

### 2.2 Research Agent

Researches approved external/internal sources and produces evidence-backed structured findings.

### 2.3 Document Agent

Creates, edits, transforms and validates document artifacts.

### 2.4 Spreadsheet/Data Agent

Analyzes tabular data, performs transformations, calculations and produces validated outputs.

### 2.5 Presentation Agent

Builds and edits presentation artifacts while respecting structure and content requirements.

### 2.6 Coding Agent

Inspects repositories, proposes changes, edits through controlled tools, runs tests and prepares patches.

### 2.7 Communication Agent

Drafts messages and invokes send actions only through policy-approved communication tools.

### 2.8 Browser Automation Agent

Operates web applications using semantic browser tools, not arbitrary uncontrolled mouse movement.

### 2.9 Computer Automation Agent

Handles supported desktop workflows through UI Automation/application adapters and visual grounding fallback.

### 2.10 QA/Verification Agent

Independently checks whether expected conditions and artifacts are correct. It must be capable of rejecting an apparently successful execution.

## 3. Common agent contract

```python
AgentRunInput(
    task_id,
    step_id,
    objective,
    context,
    permissions,
    tool_schemas,
    observation,
    recovery_history,
    output_contract,
)
```

The return value must be typed.

## 4. Planner output

```json
{
  "goal":"...",
  "steps":[
    {
      "step_id":"step_01",
      "objective":"...",
      "agent":"research-agent",
      "dependencies":[],
      "preconditions":[],
      "expected_state":{},
      "verification":[],
      "risk":"low",
      "requires_approval":false
    }
  ]
}
```

## 5. Execution Agent

The executor answers:

> Given the current step, expected state, observed state, policy and recovery history, what is the next safe operation?

It must never receive only the original user request.

## 6. Context hierarchy

Use explicit boundaries:

```text
SYSTEM POLICY
TASK INSTRUCTION
AUTHORIZED CONTEXT
RETRIEVED KNOWLEDGE
CURRENT OBSERVATION
TOOL RESULTS
RECOVERY HISTORY
USER APPROVAL
```

Untrusted documents are data, not instructions.

## 7. Agent communication

Agents should communicate through structured artifacts/events rather than hidden conversational chains.

Example:

```json
{
  "from":"spreadsheet-agent",
  "to":"document-agent",
  "artifact":"artifact://report.xlsx",
  "verification":"passed",
  "notes":["totals reconciled"]
}
```

## 8. Parallel execution

Independent steps may run in parallel.

```text
           ┌→ Research A ─┐
Plan ──────┼→ Research B ─┼→ Synthesis
           └→ Data C ─────┘
```

Dependencies must be explicit. Active task state must never be implicitly shared across unrelated tasks.

## 9. Human-in-the-loop

The agent brain must generate approval requests when policy says the next operation is consequential.

Approval is an external state transition, not a natural-language hint.

## 10. Recovery-aware intelligence

Agent decisions must include bounded recovery information:

```text
attempt_number
failure_type
previous_tool
verification_failure
allowed_alternatives
remaining_budget
```

The executor should prefer local recovery over full-task replanning where possible.

## 11. Workflow memory

Only verified traces become reusable.

Canonical representations should look like:

```text
OpenReport()
SearchCustomer(name)
CreateDraft(template)
SaveDocument(path)
AttachFile(artifact_id)
SendEmail(recipient_group)
```

not raw screen coordinates.

## 12. Open-ended capability model

“General-purpose” means the agent brain can compose new workflows from available capabilities. It does not mean arbitrary, unrestricted machine access.

The platform expands through:

```text
NEW APPLICATION
   ↓
NEW TOOL / CONNECTOR
   ↓
NEW AGENT CAPABILITY
   ↓
VERIFIER
   ↓
POLICY
   ↓
WORKFLOW COMPOSITION
```

This provides a path from a fixed MVP to a much broader agentic execution platform.


---

## 13. Memory (Phase 5 — implemented)

The agent brain now has a memory layer with four distinct classes that are
never collapsed into one store:

```text
SESSION MEMORY      bounded per-execution state (variables, observations)
KNOWLEDGE MEMORY    enterprise documents (Phase 4 RAG, autoflow_knowledge)
WORKFLOW MEMORY     verified reusable semantic workflows (SQLite +
                    autoflow_workflows Chroma collection)
GRAPH MEMORY        apps/tools/actions/artifacts/workflows relationships
```

Learning loop (verified-only):

```text
EXECUTE → OBSERVE → VERIFY
   → normalize trace into a SemanticWorkflow (no coordinates)
   → promotion policy (verification-gated; secrets/unregistered-tools rejected)
   → versioned WorkflowMemory (content-hash dedupe)
FUTURE PROMPT
   → semantic workflow search (tenant/workspace authorized)
   → compatibility check → parameter binding → validate → execute → verify
```

Retrieved workflows enter the Context Engine as `WORKFLOW_MEMORY` at
`AUTHORIZED_MEMORY` trust — they are **data**, never instructions, and can never
override system policy. Failed executions are recorded as failure statistics but
are never promoted. This is workflow learning, not model fine-tuning.


---

## 14. Dynamic Planner + Multi-Agent Runtime (Phase 6 — implemented)

The planner/executor separation is now real:

```text
PLANNER            "What is the whole job?"   -> typed PlannerOutput + graph
EXECUTION AGENTS   "What next, given state?"  -> structured AgentActionProposal
TOOL AUTHORITY     runtime validates + executes only registered tools
```

**Planning** (`planning/`): `PlannerOutput` is a strict contract; a
`RuntimeGraph` of `PlanNode`s carries mutable node status with an explicit state
machine (PENDING→READY→RUNNING→SUCCEEDED/FAILED→NEEDS_REPLAN). `validate_plan`
rejects cycles, unknown/self dependencies, duplicate ids, unknown agents,
unregistered tools, unavailable capabilities, ungranted permissions, and
high-risk nodes lacking approval/verification. `DeterministicPlanner` always
produces a valid graph; `ModelPlanner` asks the gateway for structured output
and **fails closed** to the deterministic planner on malformed output.

**Agents** (`agents/`): `SpecialistAgent` receives a bounded `AgentContext`
(never global state) and returns a structured `AgentResult` (concise reasoning
summary — no chain-of-thought). Nine agents exist; document/research/spreadsheet/
qa/presentation/coding/communication are executable, while **browser and
computer are real interfaces that return UNSUPPORTED** rather than faking
automation.

**Runtime** (`runtime/multi_agent.py`): `MultiAgentRuntime` selects ready nodes,
runs independent nodes with bounded concurrency, resolves fan-out/fan-in,
detects deadlocks, and enforces the authority chain
(propose → schema → policy → permission → approval → `ToolRegistry` execute →
observe → verify). Failures trigger bounded replanning; verified runs feed the
Phase 5 promotion pipeline. Retrieved workflow memory enters as data and never
overrides policy.


---

## 15. Tool-Calling Controller + Computer Agent (Phase 7 — implemented)

The `ComputerAutomationAgent` is now real. It reasons over a bounded
`DesktopObservation` (semantic controls, not pixels) and proposes one semantic
computer action per node; it never touches the desktop directly. The
`ToolCallingController` is the sole path from proposal to execution:

```text
ComputerAgent proposal (e.g. click role=button name=Save)
  → schema → registry → authorization → policy/risk → approval
  → ToolRegistry → WindowsUIAutomationAdapter → observation → verification
```

Safety: destructive/shell tools are never registered; application launch is
allowlisted; secrets and typed text are redacted from traces; ambiguous targets
are refused (never guessed). Live-verified on Windows with a real Notepad
workflow. Browser automation is a distinct future phase.


---

## 16. Computer-Autonomy Bundle (Phases 8–14 — implemented)

The agent brain can now drive both desktop and browser through one authority
chain. It reasons over a **fused** observation (UIA + DOM + screenshot), resolves
a semantic target (never guessing among ambiguous candidates), proposes a
semantic action, and lets the `ToolCallingController` + `AutonomyLoop` execute →
observe → verify with a bounded recovery ladder and stuck detection. Vision is
evidence (rate-limited, corroborated), never authority; deterministic OpenCV is
preferred first. Approvals bind to the exact action+observation; rate limits and
resource locks bound autonomy. Live-verified: real Notepad (UIA) and real
headless browser (Playwright).
