# AutoFlow AI — Prompts, Tools and Schemas

## 1. Prompt engineering principle

Prompts are versioned software assets. Every production prompt must have:
- owner;
- version;
- role;
- input contract;
- output schema;
- safety rules;
- evaluation suite.

Do not rely on a giant generic prompt for every agent.

## 2. Prompt layers

Every model request should be assembled from explicit layers:

```text
SYSTEM ROLE
+
POLICY
+
TASK
+
AUTHORIZED CONTEXT
+
CURRENT STEP
+
OBSERVATION
+
AVAILABLE TOOLS
+
OUTPUT CONTRACT
```

Retrieved content and tool results are lower-trust data inside this structure.

## 3. Planner prompt contract

The planner must be told:
- optimize for outcome, not conversation;
- use only authorized capabilities;
- define dependencies;
- define postconditions;
- identify approval boundaries;
- avoid invented tool names;
- return only schema-valid output.

### Planner output rule

No prose is accepted as the canonical plan.

## 4. Execution prompt contract

Inputs:
- current step;
- expected state;
- observed state;
- relevant context;
- tool catalog;
- policy;
- recovery history.

Question:

> What is the next safe operation that advances the current step toward its expected state?

The executor may return:

```json
{
  "action_type":"tool_call",
  "tool":"browser.click",
  "arguments":{"target":{"role":"button","name":"Save"}},
  "reason":"The Save control is the next required action.",
  "confidence":0.94
}
```

The `reason` is concise operational rationale, not private chain-of-thought.

## 5. Tool-calling prompt contract

The tool caller sees only the approved tools relevant to the step.

Rules:
- never invent a tool;
- fill arguments strictly according to schema;
- use enums when provided;
- stop when required information is missing;
- emit confidence;
- reject unsafe or ambiguous calls.

## 6. Verifier prompt contract

The verifier receives:
- intended outcome;
- expected state;
- observed state;
- tool result;
- artifact evidence;
- relevant source evidence.

It must answer whether the postcondition is satisfied, with structured checks.

## 7. Prompt-injection defense

Untrusted documents should be delimited as data.

Example conceptual assembly:

```text
<SYSTEM_POLICY>
...
</SYSTEM_POLICY>

<TASK>
...
</TASK>

<AUTHORIZED_CONTEXT>
...
</AUTHORIZED_CONTEXT>

<UNTRUSTED_RETRIEVED_CONTENT>
...
</UNTRUSTED_RETRIEVED_CONTENT>

<TOOL_RESULT>
...
</TOOL_RESULT>
```

No retrieved document can elevate its own authority.

## 8. Tool schema standard

Every tool definition should specify:

```text
name
description
input_schema
risk_class
permission_scope
requires_approval
timeout
retry_policy
idempotency
executor
verifier
```

## 9. Schema versioning

Schemas must be versioned independently from prompts.

Example:

```text
plan.v1
plan.v2
execution_action.v1
verification_result.v1
```

Backward compatibility should be preserved where practical.

## 10. Validation pipeline

```text
MODEL OUTPUT
 ↓
JSON PARSE
 ↓
SCHEMA VALIDATION
 ↓
SEMANTIC VALIDATION
 ↓
POLICY VALIDATION
 ↓
EXECUTABLE
```

A syntactically valid JSON object is not necessarily semantically valid.

## 11. Prompt tests

Every prompt version must be tested against:
- normal tasks;
- ambiguous tasks;
- missing context;
- malicious documents;
- invalid tool requests;
- approval boundaries;
- recovery scenarios;
- long-context tasks.

## 12. Structured output repair

Repair is allowed only for formatting/schema problems and within a bounded attempt count. The system must not let repair silently change task intent or permissions.
