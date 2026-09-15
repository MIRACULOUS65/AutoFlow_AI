# AutoFlow AI — AI/ML Architecture

## 1. Mission

The AI/ML layer turns human intent into structured decisions that the execution system can safely act upon.

It is the **brain**, not the hands.

## 2. AI/ML Topology

```text
User Goal
   ↓
Intent Normalizer
   ↓
Context Builder
   ↓
Planner Agent
   ↓
Task Graph
   ↓
Model Router
   ↓
Specialist Agents
   ↓
Execution Agent
   ↓
Tool-Calling Controller
   ↓
Verifier
   ↓
Recovery / Replanning
```

Every model invocation is mediated by the Model Gateway.

## 3. Model Gateway

The gateway provides one interface:

```python
class ModelProvider:
    async def generate(self, request): ...
    async def stream(self, request): ...
    async def embed(self, request): ...
    async def health(self): ...
```

The gateway normalizes:

```text
provider
model
capabilities
structured-output support
vision support
tool-calling support
context capacity
latency
cost
health
policy eligibility
```

Agents request capabilities, not provider-specific implementation details.

## 4. Planner Model

The Planner answers:

> What is the whole job?

Input:

```text
normalized goal
constraints
workspace context
authorized knowledge
available agents
available tools
policy profile
```

Output is strict structured JSON.

```json
{
  "goal": "...",
  "steps": [
    {
      "step_id": "step_01",
      "objective": "...",
      "agent": "data-analysis-agent",
      "dependencies": [],
      "preconditions": [],
      "expected_state": {},
      "tools": [],
      "verification": [],
      "risk": "low"
    }
  ]
}
```

The planner never directly executes a side effect.

## 5. Execution Agent

The Execution Agent answers:

> Given what has actually happened, what should happen next?

It receives the current state rather than relying on the original prompt.

```text
current step
expected state
observed state
authorized context
available tools
policy
attempt history
verification failures
recovery budget
```

It may produce:

```text
continue
request tool
request observation
retry
recover
replan bounded suffix
pause
complete
```

## 6. Tool-Calling Controller

The tool controller maps semantic intent to an approved tool call.

```text
semantic action
   ↓
allowed tool catalog
   ↓
schema-constrained selection
   ↓
argument generation
   ↓
confidence / validation
```

A small specialized model may be used here because the controller does not need to solve the whole business problem.

## 7. Agent Profiles

Agents share infrastructure but specialize their reasoning.

```text
Planner
Research
Document
Spreadsheet
Presentation
Coding
Data Analysis
Communication
Computer Automation
Verification / QA
```

Each agent declares:

```text
capabilities
allowed tools
input schema
output schema
model policy
risk policy
verification policy
recovery budget
```

## 8. Prompt Architecture

The runtime should keep context classes separate:

```text
SYSTEM POLICY
TASK INSTRUCTION
AUTHORIZED CONTEXT
RETRIEVED DATA
CURRENT OBSERVATION
TOOL SCHEMAS
TOOL RESULTS
APPROVAL STATE
```

Retrieved documents and tool results are data, not instruction authority.

## 9. Structured Outputs

All consequential model outputs must be schema-validated.

```text
model output
  ↓
parse
  ↓
JSON Schema / Pydantic
  ↓
semantic checks
  ↓
policy checks
  ↓
accepted or rejected
```

Malformed output should produce a controlled failure, not silent coercion into an action.

## 10. Context Construction

The model should receive the smallest sufficient context:

```text
goal
current step
relevant knowledge
relevant artifacts
current state
approved tools
policy
verification requirements
```

Do not dump the entire company knowledge base or full execution history into every call.

## 11. RAG Interface

AI/ML calls a knowledge interface rather than directly depending on a vector database implementation.

```python
search(query, identity, workspace, filters) -> Evidence[]
```

Each evidence object includes provenance and authorization metadata.

## 12. Computer-Use Intelligence

Computer-use reasoning combines:

```text
DOM / accessibility state
application metadata
screenshot / VLM
workflow history
current variables
```

The model should identify semantic targets such as:

```json
{
  "role": "button",
  "name": "Save",
  "confidence": 0.96
}
```

The runtime independently resolves and validates the target before execution.

## 13. Recovery Intelligence

Recovery should use structured failure signals.

```text
Failure
 ↓
classify
 ↓
observe
 ↓
re-resolve
 ↓
choose alternate safe action
 ↓
verify
 ↓
replan affected suffix if necessary
```

The model receives failure evidence and a bounded recovery budget.

## 14. Model Selection Strategy

Model routing score should consider:

```text
capability match
context fit
structured-output reliability
tool-call reliability
vision compatibility
latency
cost
provider health
policy
historical evaluation score
```

The routing layer should store measured results so model choice improves from evidence rather than intuition.

## 15. AI/ML Testing

Test:

```text
planner correctness
schema compliance
tool selection accuracy
argument validity
retrieval relevance
injection resistance
visual grounding
recovery decisions
verification judgment
multi-agent handoffs
```

AI quality is measured at the workflow level, not only the token/output level.

## 16. Core AI/ML Invariants

```text
LLMs never bypass policy.
LLMs never execute unrestricted functions.
LLMs never own durable workflow state by themselves.
LLMs cannot silently modify an approved action.
Every consequential output is typed.
Every material action has verification.
```
