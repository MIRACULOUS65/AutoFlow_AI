# AutoFlow AI — AI/ML Product Requirements Document

**Status:** Implementation-ready AI/ML baseline  
**Scope:** `ai-ml/` only  
**Role:** Headless intelligence, planning, memory, agent orchestration, tool selection, workflow generation, verification, recovery and evaluation core.  
**Desktop dependency:** None. The AI/ML system must run independently through Python APIs/CLI before Electron is integrated.

---

## 1. Purpose

The AI/ML subsystem is the actual operating brain of AutoFlow AI. It must turn a single natural-language request into a complete, controlled and verifiable workflow.

The system is not a chat wrapper. The expected behavior is:

```text
ONE PROMPT
   ↓
UNDERSTAND INTENT
   ↓
RESOLVE USER / WORKSPACE / PERMISSIONS
   ↓
RETRIEVE AUTHORIZED KNOWLEDGE + MEMORY
   ↓
BUILD CONTEXT
   ↓
GENERATE SEMANTIC WORKFLOW
   ↓
VALIDATE PLAN
   ↓
ASSIGN AGENTS
   ↓
ROUTE MODELS
   ↓
EXECUTE STEP BY STEP
   ↓
CALL APPROVED TOOLS
   ↓
OBSERVE REAL STATE
   ↓
VERIFY POSTCONDITIONS
   ↓
RECOVER / REPLAN WHEN NEEDED
   ↓
REQUEST HUMAN APPROVAL WHEN REQUIRED
   ↓
DELIVER VERIFIED RESULT
   ↓
SAVE VERIFIED WORKFLOW MEMORY
```

The AI/ML product is successful when the same engine can execute a broad range of supported tasks without requiring a new hard-coded workflow for every request.

---

# 2. Product Contract

### User contract

The user should be able to say something as simple as:

> “Take this document, edit the wording as discussed, save the same file, create an email to the sender, attach the edited document, and send it to them after asking me once.”

AutoFlow must discover the necessary workflow instead of requiring the user to manually select agents or tools.

### System contract

The system must:

1. identify the source file and preserve its identity when the request means “edit this file”;
2. inspect the document before changing it;
3. create an execution plan with dependencies and expected states;
4. route document work to the document agent;
5. create or edit the artifact deterministically;
6. verify the edited artifact;
7. identify the intended email sender/recipient from authorized context or connected mail data;
8. create the email as a draft;
9. attach the verified artifact;
10. stop at the configured approval checkpoint;
11. continue only after approval;
12. send through the approved Gmail/mail connector;
13. verify that the send operation actually occurred;
14. return the result, artifact and trace;
15. optionally promote the verified semantic procedure into workflow memory.

The AI/ML layer itself does **not** directly hold a Gmail password or perform an unrestricted SMTP operation. It requests a typed communication tool; the execution layer performs the actual side effect using a secure connector.

---

# 3. Core Architecture

```text
┌───────────────────────────────────────────────────────────────┐
│                       AUTOFLOW AI / AI-ML                    │
├───────────────────────────────────────────────────────────────┤
│  Intent Layer                                                │
│  └─ normalization, entities, constraints, ambiguity         │
│                                                               │
│  Context Layer                                               │
│  └─ task state + permissions + knowledge + memory + tools    │
│                                                               │
│  Memory / RAG Layer                                          │
│  └─ ChromaDB + metadata + semantic search + reranking       │
│                                                               │
│  Agent Brain                                                 │
│  └─ planner + dispatcher + execution agent + QA             │
│                                                               │
│  Model Gateway                                               │
│  └─ provider adapters + model registry + routing            │
│                                                               │
│  Tool Calling                                                │
│  └─ semantic action → typed tool request                    │
│                                                               │
│  Execution Intelligence                                     │
│  └─ state-aware decisions + observations + recovery         │
│                                                               │
│  Workflow Intelligence                                       │
│  └─ semantic workflow generation + normalization + memory    │
│                                                               │
│  Safety / Verification                                       │
│  └─ policy, confidence, approval, verification, limits      │
└───────────────────────────────────────────────────────────────┘
                           │
                           ▼
                 DETERMINISTIC TOOL RUNTIME
```

### Hard boundary

```text
MODEL OUTPUT
    ↓
SCHEMA VALIDATION
    ↓
POLICY / PERMISSION CHECK
    ↓
TOOL EXECUTION
    ↓
OBSERVATION
    ↓
VERIFICATION
```

No model output is itself an authoritative side effect.

---

# 4. AI/ML Layers

## Layer 1 — Request / Intent

Responsibilities:

- parse natural language;
- identify the desired outcome;
- identify referenced files, people, applications and services;
- extract constraints;
- detect ambiguity;
- classify task type;
- estimate risk;
- determine required capabilities.

Output:

```json
{
  "intent": "edit_document_and_email",
  "goal": "Edit the supplied document and send the edited version to its sender",
  "entities": {
    "source_file": "attachment:0",
    "sender": "unknown_until_resolved"
  },
  "constraints": [
    "preserve_same_file_identity where possible",
    "ask_before_external_send"
  ],
  "capabilities": [
    "document_editing",
    "email_draft",
    "email_send"
  ],
  "risk": "high_at_send_boundary"
}
```

## Layer 2 — Identity, Scope and Permission

The model cannot decide its own authority.

Resolve:

- user;
- organization;
- workspace;
- available applications;
- allowed tools;
- connector scopes;
- accessible files;
- approval authority.

Authorization is applied before knowledge retrieval and again before tool execution.

## Layer 3 — Context Assembly

Context is assembled from distinct channels:

```text
SYSTEM RULES
    ↓
TASK GOAL
    ↓
USER CONSTRAINTS
    ↓
AUTHORIZED KNOWLEDGE
    ↓
RETRIEVED WORKFLOW MEMORY
    ↓
CURRENT TASK STATE
    ↓
CURRENT STEP
    ↓
CURRENT OBSERVATION
    ↓
AVAILABLE TOOLS
    ↓
RECOVERY HISTORY
    ↓
APPROVAL STATE
```

Untrusted retrieved data must remain data and must never silently become higher-priority instructions.

## Layer 4 — Knowledge / RAG

The knowledge layer supplies relevant facts, procedures and examples.

Initial storage model:

- **ChromaDB** for vector retrieval;
- metadata filters for tenant/workspace/source/access scope;
- relational persistence for canonical metadata and workflow records;
- optional graph relationships later.

Documents are indexed as chunks with metadata such as:

```text
chunk_id
source_id
tenant_id
workspace_id
source_type
source_version
page / section
permissions
provenance
created_at
updated_at
embedding_model
content_hash
```

### Retrieval flow

```text
QUERY
 ↓
IDENTITY / SCOPE FILTER
 ↓
EMBED QUERY
 ↓
CHROMADB SEMANTIC SEARCH
 ↓
METADATA FILTER
 ↓
OPTIONAL RERANK
 ↓
DEDUPLICATE
 ↓
PROVENANCE ATTACHMENT
 ↓
CONTEXT BUDGETING
 ↓
MODEL INPUT
```

Similarity alone is never an authorization decision.

## Layer 5 — Memory

Memory is intentionally separated into:

```text
SESSION MEMORY
  current task / variables / recent observations

WORKFLOW MEMORY
  verified semantic workflows / successful recovery paths

KNOWLEDGE MEMORY
  company documents / SOPs / policies / manuals

EXECUTION HISTORY
  prior traces / metrics / outcomes
```

Only verified workflow traces become canonical reusable workflows.

## Layer 6 — Planning

Planner answers:

> What sequence of work is necessary to reach the requested outcome?

The planner generates a **semantic DAG**, not a list of prose instructions.

Every step contains at minimum:

```text
step_id
objective
agent
inputs
dependencies
preconditions
expected_state
tool_capabilities
verification
risk
approval_requirement
retry_budget
replan_budget
```

## Layer 7 — Agent Assignment

The planner assigns specialized agents according to capability.

Initial agent set:

1. Research Agent
2. Document Agent
3. Spreadsheet/Data Agent
4. Presentation Agent
5. Coding Agent
6. Communication Agent
7. Browser Automation Agent
8. Computer Automation Agent
9. QA/Verification Agent

System-level controllers are separate from those business agents:

```text
Planner
Execution Agent
Tool-Calling Controller
Verifier
Recovery Controller
Model Router
```

These are runtime roles, not necessarily visible “chat agents.”

## Layer 8 — Model Routing

Agents request capabilities rather than hard-coding a provider.

Example:

```json
{
  "capabilities": ["reasoning", "structured_output"],
  "context_tokens_required": 12000,
  "risk": "medium",
  "latency_budget_ms": 8000
}
```

The router selects an eligible model using:

- capability;
- context capacity;
- modality;
- structured-output reliability;
- tool-calling support;
- current provider health;
- latency;
- cost where available;
- policy;
- fallback compatibility.

## Layer 9 — Tool Calling

The model proposes a semantic action.

Example:

```json
{
  "action": "document.replace_text",
  "arguments": {
    "file_id": "file_123",
    "find": "old phrase",
    "replace": "new phrase"
  },
  "confidence": 0.98
}
```

The tool registry determines the actual executable function.

The model may not invent arbitrary function names.

## Layer 10 — Execution Intelligence

The Execution Agent is state-aware.

It receives:

```text
current plan step
current application/tool state
expected state
observed state
available tools
permissions
knowledge
recovery history
remaining budgets
```

It decides the next safe semantic operation, not the final unrestricted machine action.

## Layer 11 — Observation

After a side effect, the runtime collects real state.

Examples:

- file exists and changed hash;
- DOCX opens successfully;
- Gmail draft exists;
- attachment is present;
- browser page changed;
- application state changed;
- API resource now has expected value.

## Layer 12 — Verification

Every material step has postconditions.

Verification types:

```text
STRUCTURAL
SEMANTIC
DATA
UI / APPLICATION STATE
ARTIFACT
EXTERNAL SIDE EFFECT
```

Example:

```text
email.send returns success
        ≠
email was successfully verified
```

Verification should use independent checks where practical.

## Layer 13 — Recovery

```text
FAILURE
 ↓
CLASSIFY
 ↓
RETRY IF TRANSIENT
 ↓
RE-OBSERVE
 ↓
RE-RESOLVE
 ↓
ALTERNATE SAFE METHOD
 ↓
REPLAN FAILED SUFFIX
 ↓
HUMAN ESCALATION
```

Recovery is bounded by:

- attempts;
- elapsed time;
- tool calls;
- model calls;
- replans;
- cost where measurable.

## Layer 14 — Workflow Learning

Successful execution becomes a candidate workflow only after verification.

```text
EXECUTION TRACE
 ↓
NORMALIZE INTO SEMANTIC ACTIONS
 ↓
REMOVE EPHEMERAL DATA
 ↓
VERIFY OUTCOME
 ↓
ATTACH PROVENANCE
 ↓
VERSION WORKFLOW
 ↓
STORE
 ↓
RETRIEVE FOR FUTURE SIMILAR TASKS
```

Example canonical workflow:

```text
OpenDocument(source_file)
EditDocument(changes)
SaveDocument(source_file)
CreateEmail(recipient)
AttachArtifact(edited_document)
RequestApproval(send_email)
SendEmail(recipient, attachment)
VerifyEmailSent()
```

Not:

```text
click(842, 517)
click(1121, 603)
click(945, 700)
```

---

# 5. Token, Attention and Context Management

The AI/ML subsystem must treat context as a managed resource, not as an unlimited prompt.

## 5.1 Context budget

Every model call should be assembled against a token budget:

```text
SYSTEM / SAFETY
+ TASK
+ RELEVANT MEMORY
+ RAG EVIDENCE
+ CURRENT STEP
+ OBSERVATION
+ TOOL SCHEMAS
+ RECOVERY HISTORY
+ OUTPUT CONTRACT
≤ MODEL CONTEXT LIMIT
```

The system should never blindly inject all conversation history, all documents or all tool definitions.

## 5.2 Context prioritization

When context is too large, priority is:

1. system safety/policy;
2. current task objective;
3. current step and expected state;
4. required permissions;
5. immediate observation;
6. task-critical retrieved evidence;
7. directly relevant workflow memory;
8. compact execution history;
9. optional background context.

## 5.3 Attention-aware context design

The system cannot directly control a model's internal attention mechanism, but it can improve effective attention by:

- placing critical instructions in stable sections;
- minimizing irrelevant retrieval;
- labeling source and trust level;
- separating data from instructions;
- summarizing stale history;
- using structured state instead of prose repetition;
- keeping tool schemas minimal;
- passing only the tools needed for the current step.

## 5.4 Context compaction

Long-running tasks should periodically create a compact state summary:

```json
{
  "completed": ["step_01", "step_02"],
  "active_step": "step_03",
  "important_facts": [],
  "artifacts": [],
  "open_approvals": [],
  "recovery_history": [],
  "next_required_condition": "..."
}
```

The compaction must preserve machine-critical state even if natural-language history is discarded.

---

# 6. Hallucination and Grounding Requirements

The AI/ML subsystem must be designed so that unsupported model claims do not become execution facts.

## 6.1 Grounding rules

- factual business data must come from authorized context or tools;
- file identity must be resolved from actual filesystem/connector state;
- application state must come from observation;
- external actions must be confirmed by the connector/runtime;
- generated content must be labeled as generated until verified;
- the model must not fabricate tool results;
- the model must not invent successful execution.

## 6.2 Evidence-linked outputs

For important claims, the runtime should retain:

```text
claim
source IDs
source version
retrieval event
agent/model
verification state
```

## 6.3 No-evidence behavior

When required information cannot be grounded:

```text
UNKNOWN
 ↓
RETRIEVE / OBSERVE / ASK
 ↓
STILL UNKNOWN?
 ↓
PAUSE OR ESCALATE
```

The agent must prefer “I need more information” or an approval/clarification state over invented facts.

---

# 7. Semantic Search Requirements

Semantic search is used for two primary purposes:

### Knowledge retrieval

Find relevant authorized information from indexed documents.

### Workflow retrieval

Find previously verified workflows that may accelerate a new task.

Workflow retrieval query example:

```text
“edit the attached Word document, preserve formatting, save it and email it to the original sender after approval”
```

The system may retrieve:

```text
workflow: EditAndReturnDocument
workflow: EditDocumentAndEmail
workflow: PreserveSourceFileFormat
```

The retrieved workflow is a **candidate**, not an unconditional instruction. It must be revalidated against the current task, tools, permissions and state.

---

# 8. Semantic Workflow Generation

The planner generates workflows in semantic operations.

## 8.1 Operation model

```json
{
  "operation": "document.edit",
  "target": {
    "type": "file",
    "identity": "attachment:0"
  },
  "inputs": {},
  "preconditions": [],
  "postconditions": [],
  "risk": "low"
}
```

## 8.2 Workflow versioning

Every generated workflow gets:

```text
workflow_id
version
source_task_id
created_at
plan_hash
input_signature
verification_summary
provenance
```

## 8.3 Workflow reuse

Reuse is allowed only when:

- intent is sufficiently compatible;
- required capabilities exist;
- permissions are compatible;
- current application/tool state can satisfy preconditions;
- the workflow is not revoked;
- previous execution quality meets promotion rules.

---

# 9. Agent Interaction Model

Agents do not talk through uncontrolled natural-language conversations.

They exchange typed messages, artifacts and execution events.

Example:

```text
Planner
  ↓ plan
Document Agent
  ↓ verified artifact
Communication Agent
  ↓ draft + attachment
Approval Controller
  ↓ approved action
Communication Agent
  ↓ send request
Tool Runtime
  ↓ result
QA Agent
  ↓ verification
Workflow Memory
```

Agent-to-agent message example:

```json
{
  "from_agent": "document-agent",
  "to_agent": "communication-agent",
  "type": "artifact.ready",
  "artifact_id": "artifact_456",
  "verification": "passed",
  "content_hash": "..."
}
```

---

# 10. Workflow / Automation Requirements

AutoFlow must represent the workflow as a persistent stateful process.

### Standard execution lifecycle

```text
CREATE TASK
 ↓
NORMALIZE
 ↓
RETRIEVE
 ↓
PLAN
 ↓
VALIDATE
 ↓
READY
 ↓
RUN STEP
 ↓
OBSERVE
 ↓
VERIFY
 ↓
NEXT STEP
 ↓
...
 ↓
FINAL VERIFY
 ↓
DELIVER
```

### Automation controls

Each execution supports:

- pause;
- resume;
- cancel;
- approval;
- retry;
- bounded recovery;
- replan;
- timeout;
- cost/tool-call budget.

---

# 11. Required End-to-End Workflow Families

Before desktop integration, the AI/ML engine must prove the following classes.

## A. File workflow

```text
Prompt
→ find file
→ inspect
→ edit
→ save
→ verify
→ return
```

## B. Document + email workflow

```text
Prompt
→ identify document
→ edit document
→ verify document
→ identify recipient
→ create email
→ attach document
→ approval
→ send
→ verify send
→ return
```

## C. Knowledge workflow

```text
Prompt
→ identify question
→ permission filter
→ semantic search
→ retrieve evidence
→ reason over evidence
→ produce answer with provenance
```

## D. Browser workflow

```text
Prompt
→ plan
→ open controlled browser
→ inspect state
→ resolve semantic target
→ action
→ observe
→ verify
→ recover if needed
```

## E. Desktop workflow

```text
Prompt
→ identify application
→ inspect UI
→ resolve control
→ action
→ observe
→ verify
→ recover/replan
```

## F. Coding workflow

```text
Prompt
→ inspect repository
→ reproduce issue
→ plan fix
→ edit through controlled tools
→ run tests
→ verify
→ generate patch
```

## G. Multi-agent workflow

```text
Prompt
→ planner
→ parallel specialist steps
→ artifacts
→ synthesis
→ verification
→ final output
```

---

# 12. Human Approval Semantics

Approval is part of execution state.

Approval must bind to:

```text
execution_id
plan_version
action_hash
risk_class
summary
evidence
expires_at
```

Example:

```text
Document edited ✓
Email draft prepared ✓
Recipient resolved ✓
Attachment verified ✓

SEND EMAIL
Risk: external communication

[ APPROVE ]   [ REJECT ]
```

If the send operation changes materially after approval, a new approval is required.

---

# 13. Initial AI/ML Build Phases

> **Implementation status (2026-09-12).** Contracts + vertical slice (Golden 01)
> + Phase 2 model gateway (+SSE streaming) + Phase 3 context engine + Phase 4
> ChromaDB RAG + Phase 5 Memory + Phase 6 Dynamic Planner + Multi-Agent Runtime
> + **Phase 7 Tool-Calling Controller + Windows Computer-Use** are complete. A
> `ToolCallingController` enforces the authority chain; a real
> `WindowsUIAutomationAdapter` drives the desktop semantically (live-verified
> with Notepad); the `ComputerAutomationAgent` runs inside the multi-agent
> runtime. Browser automation remains a separate future phase (not faked).
> **352 tests pass** (incl. 2 real live-desktop tests). Email and the full
> stress harness are not yet implemented.
>
> **(Superseded status line below kept for history.)** Contracts + vertical
> slice (Golden 01) + Phase 2 model gateway (+SSE streaming) + Phase 3 context
> engine + Phase 4 ChromaDB RAG + Phase 5 Memory + **Phase 6 Dynamic Planner +
> Multi-Agent Runtime** are complete. A typed planner produces a validated task graph; a
> specialist-agent registry + `MultiAgentRuntime` schedule it with bounded
> concurrency, dependency resolution, verification and bounded replanning, while
> preserving the authority chain (agents propose; the runtime validates and
> executes only registered tools). Browser/computer agents are real interfaces
> that return UNSUPPORTED (not faked). **324 tests pass.** Real browser/desktop
> automation, email, and the full stress harness are **not yet implemented**.
>
> **(Superseded status line below kept for history.)** Contracts + vertical
> slice (Golden 01) + Phase 2 model gateway (+SSE streaming) + Phase 3 context
> engine + Phase 4 ChromaDB RAG + **Phase 5 Memory** are complete. Verified workflow memory
> (SQLite + a dedicated `autoflow_workflows` Chroma collection) learns reusable
> semantic workflows from verified executions (verification-gated promotion,
> never failed/unverified), retrieves them semantically with tenant/workspace
> authorization, and binds parameters for reuse — integrated into the context
> engine as data. Session and graph memory exist too. **283 tests pass.** This
> is workflow learning, not model-weight training. Real browser/desktop
> automation, email, dynamic multi-agent planner, and the full stress harness
> are **not yet implemented**.
>
> **(Superseded status lines below kept for history.)** Contracts + vertical
> slice (Golden 01) + Phase 2 model gateway + Phase 3 context engine + **Phase 4
> ChromaDB RAG** are complete. Real persistent ChromaDB provides authorized semantic retrieval with
> evidence/provenance and physical tenant/workspace/permission isolation, wired
> into the context engine (retrieved knowledge is DATA, never instructions).
> Embeddings run through a provider interface (offline deterministic local +
> OpenAI-compatible remote for NVIDIA/ModelScope). **244 tests pass.** Persistent
> memory (Phase 5), real browser/desktop automation, email, and the full stress
> harness are **not yet implemented**.
>
> **(Superseded status line below kept for history.)** Contracts + vertical slice
> (Golden 01) + **Phase 2 real model gateway** + **Phase 3 context engine** are
> complete.
> A real NVIDIA (OpenAI-compatible) provider is live-verified end-to-end; the
> gateway is provider-neutral with retry/fallback/health and a deterministic
> local provider for offline/tests. The **context engine** now assembles
> budgeted, trust-separated, permission-filtered, deterministically-hashed
> context before every model call (retrieved/tool/external content is always
> framed as DATA, never instructions). Driven headlessly by `autoflow run`,
> `autoflow model test`, and `autoflow context inspect|estimate|validate`.
> **208 tests pass.** RAG/ChromaDB, persistent memory, real browser/desktop
> automation, email, and the full stress harness are **not yet implemented**.
> See `docs/IMPLEMENTATION_STATUS.md` and `ai-ml/docs/TASKS.md`.

## Phase 0 — Contracts

Build typed schemas and test fixtures first.

Deliver:

- TaskRequest;
- Intent;
- Plan;
- AgentRun;
- ToolCall;
- Observation;
- VerificationResult;
- ApprovalRequest;
- RecoveryDecision;
- WorkflowMemory;
- execution events.

**Test:** invalid schemas fail; valid schemas round-trip exactly.

## Phase 1 — Model Gateway

Build:

- provider interface;
- model registry;
- routing;
- retries;
- streaming;
- structured output;
- health checks;
- environment-based secrets.

**Test:** one CLI prompt can produce a validated model result through a provider-neutral interface.

## Phase 2 — Agent Brain

Build:

- intent normalization;
- context assembly;
- planner;
- agent registry;
- execution-agent loop;
- QA/verifier controller.

**Test:** complex prompts produce valid semantic DAGs and agent assignments.

## Phase 3 — RAG + ChromaDB

Build:

- document ingestion;
- chunking;
- metadata;
- embeddings;
- ChromaDB collections;
- semantic search;
- permission filters;
- reranking;
- provenance.

**Test:** relevant documents are retrieved; unauthorized documents never enter model context.

## Phase 4 — Tool Calling

Build:

- tool registry;
- JSON/Pydantic schemas;
- tool capability matching;
- confidence gating;
- argument validation;
- bounded repair.

**Test:** the model can only request registered tools and invalid arguments fail safely.

## Phase 5 — Deterministic Execution Runtime

Build:

- filesystem;
- document;
- data;
- API/HTTP;
- browser;
- desktop;
- communication;
- sandboxed code tools.

**Test:** headless workflows reach real verified outcomes without Electron.

## Phase 6 — Verification + Recovery

Build:

- postcondition engine;
- recovery classifier;
- retry;
- re-observe;
- re-resolve;
- alternate path;
- bounded replan;
- human escalation.

**Test:** injected failures recover without unsafe duplicate effects.

## Phase 7 — Semantic Workflow Memory

Build:

- trace normalization;
- workflow generation;
- workflow hashing/versioning;
- semantic workflow retrieval;
- promotion rules;
- workflow reuse tests.

**Test:** a verified workflow can accelerate an equivalent future task without copying stale assumptions.

## Phase 8 — Full AI/ML Stress Harness

Build:

- golden tasks;
- benchmark runner;
- chaos scenarios;
- concurrency runner;
- adversarial tests;
- model comparison;
- release reports.

**Exit gate:** the AI/ML engine is stable enough for backend exposure.

---

# 14. Required Test Plan

## 14.1 Contract tests

Test:

- schema validation;
- enum validity;
- event ordering;
- plan versioning;
- hash stability;
- serialization compatibility.

## 14.2 Model tests

Test each registered model/provider for:

- structured JSON reliability;
- malformed output;
- tool-call validity;
- timeout;
- provider failure;
- context overflow;
- streaming interruption;
- token-budget compliance.

## 14.3 Planner tests

Test prompts that are:

- simple;
- multi-step;
- ambiguous;
- parallelizable;
- sequential;
- approval-sensitive;
- impossible;
- missing required data;
- contradictory.

## 14.4 RAG tests

Test:

- semantic relevance;
- metadata filtering;
- tenant isolation;
- stale document versions;
- duplicate chunks;
- irrelevant retrieval;
- prompt-injected documents;
- citation/provenance preservation;
- empty retrieval behavior.

## 14.5 Hallucination tests

Inject scenarios where:

- the requested file does not exist;
- the recipient cannot be resolved;
- the connector returns an unknown state;
- a tool claims success but the resource did not change;
- retrieved knowledge conflicts;
- a document contains malicious instructions.

Expected behavior is **observe/retrieve/ask/block**, never fabricate completion.

## 14.6 Tool tests

Test:

- unknown tool;
- wrong schema;
- missing required argument;
- unauthorized tool;
- incorrect permission scope;
- high-risk action without approval;
- stale approval;
- changed action hash;
- duplicate request.

## 14.7 Execution tests

Run workflows with:

- normal success;
- transient failure;
- permanent failure;
- timeout;
- process restart;
- browser crash;
- stale state;
- concurrent tasks;
- cancel/resume.

## 14.8 Browser/computer tests

Use controlled test applications.

Test:

- semantic target selection;
- DOM metadata changes;
- accessibility tree changes;
- renamed buttons;
- moved controls;
- visual grounding fallback;
- wrong-target rejection;
- post-action verification.

## 14.9 Approval tests

Test:

```text
request approval
→ approve
→ resume
→ execute
→ verify
```

and:

```text
request approval
→ reject
→ terminate safely
```

Also test:

```text
approve action A
→ agent changes to action B
→ action B must require new approval
```

## 14.10 Workflow memory tests

Test:

- semantic workflow creation;
- workflow retrieval;
- version compatibility;
- invalidation;
- stale workflow rejection;
- successful reuse;
- failed workflow not promoted.

## 14.11 Security/adversarial tests

Test:

- prompt injection;
- tool injection;
- cross-tenant retrieval;
- secret leakage;
- approval bypass;
- confused deputy;
- malicious attachments;
- malicious web content;
- arbitrary shell/code attempts.

## 14.12 Endurance tests

Run long-lived tasks with:

- repeated model calls;
- many tool calls;
- multiple approvals;
- large context;
- transient provider faults;
- multiple concurrent executions.

The goal is to detect state drift, memory growth, duplicate actions and recovery loops.

---

# 15. Golden End-to-End Tests

The following workflows are mandatory release scenarios.

### Golden 01 — Edit same file

```text
“Edit this Word file using the requested wording and save the edited version as the same file.”
```

Expected:

```text
attachment resolved
→ source read
→ edit applied
→ same-file requirement respected
→ file saved
→ file re-opened
→ content verified
```

### Golden 02 — Edit + Gmail

```text
“Edit this document, create an email to the sender, attach the edited document and send it after asking me once.”
```

Expected:

```text
resolve document
→ edit
→ verify
→ resolve sender
→ compose email
→ attach
→ verify draft
→ approval
→ send
→ verify send
→ final result
```

### Golden 03 — Knowledge-grounded task

```text
“Using our approved finance procedure, create the monthly closing checklist.”
```

Expected:

```text
permission filter
→ ChromaDB search
→ evidence retrieval
→ grounded plan
→ artifact generation
→ evidence/provenance
→ verification
```

### Golden 04 — Browser automation

```text
“Find the approved order on the test portal, download the invoice and report the total.”
```

Expected:

```text
browser open
→ inspect state
→ search
→ resolve target
→ download
→ verify file
→ extract total
→ return evidence
```

### Golden 05 — Recovery

Same browser task, but the button text or UI layout changes.

Expected:

```text
verification failure
→ re-observe
→ re-resolve
→ retry alternate semantic target
→ verify
```

### Golden 06 — Multi-agent

```text
“Analyze these sales files, create a management report, summarize the findings and prepare an email draft.”
```

Expected parallelism where safe:

```text
                ┌→ Data Agent ─────┐
Planner ────────┼→ Research Agent ─┼→ QA
                └→ Document Agent ─┘
                                  ↓
                              Communication
```

---

# 16. Evaluation Metrics

The AI/ML release report should track:

```text
Plan validity rate
Tool-call validity rate
Verified task completion rate
Recovery success rate
False verification rate
Unsafe action block rate
RAG retrieval precision
Workflow reuse success rate
Approval correctness
Duplicate side-effect rate
Cross-tenant leakage rate
Average model latency
Average task latency
Model/tool call count
Context/token usage
```

No absolute reliability claim is accepted without measured test evidence.

---

# 17. Definition of Done

The AI/ML subsystem is ready for backend integration only when:

```text
[ ] CLI can submit a task without Electron
[ ] Intent normalization works
[ ] Planner generates valid semantic DAGs
[ ] Agents receive typed contracts
[ ] ChromaDB retrieval works with permission filtering
[ ] Context is token-budgeted
[ ] Model routing is provider-agnostic
[ ] Tool calls are schema-validated
[ ] Deterministic runtimes perform side effects
[ ] Observation follows consequential actions
[ ] Verification is mandatory for material steps
[ ] Human approval pauses/resumes work correctly
[ ] Recovery and bounded replanning work
[ ] Semantic workflows can be generated and versioned
[ ] Verified workflows can be saved and retrieved
[ ] Hallucination/fabrication tests pass
[ ] Prompt-injection tests pass
[ ] Multi-task isolation tests pass
[ ] Browser automation works in controlled fixtures
[ ] Desktop automation works in controlled fixtures
[ ] End-to-end document→email task works in a controlled environment
[ ] Stress suite is repeatable from CLI
[ ] Evaluation results are persisted per build/model version
```

---

# 18. CLI / Headless Target

The subsystem must eventually support a workflow similar to:

```bash
# basic execution
autoflow run "edit this document and save it"

# inspect plan
autoflow plan --task task.json

# run semantic search
autoflow memory search "how do we prepare the finance report"

# inspect workflow memory
autoflow workflow search "edit document and email"

# execute a golden task
autoflow-eval task golden/email_approval

# run the full AI/ML suite
autoflow-eval suite ai-ml

# run recovery tests
autoflow-eval chaos --scenario browser_ui_changed
```

The Electron application should later become another client of these same capabilities.

---

# 19. Final AI/ML Product Definition

AutoFlow AI's AI/ML subsystem is a **general-purpose, stateful agent execution engine**.

Its intelligence comes from the combination of:

```text
Foundation Models
     +
Intent Understanding
     +
Context Engineering
     +
ChromaDB Semantic Retrieval
     +
Company Knowledge
     +
Verified Workflow Memory
     +
Multi-Agent Planning
     +
Model Routing
     +
Structured Tool Calling
     +
Deterministic Tools
     +
Computer Use
     +
Observation
     +
Verification
     +
Human Approval
     +
Recovery / Replanning
     +
Workflow Learning
     +
Evaluation
     =
AutoFlow AI
```

The central engineering principle remains:

> **The model decides what should happen next. The system decides whether it is allowed. Deterministic tools perform the action. Observation proves what happened. Verification decides whether the goal was actually achieved.**
