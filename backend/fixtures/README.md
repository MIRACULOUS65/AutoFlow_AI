# Contract Fixtures

Shared, versioned request/response fixtures for cross-team contract testing
(backend ↔ orchestrator ↔ agents). Each `*.json` is a `TaskRequest`-shaped
payload plus notes on the expected control-plane behavior.

These are the canonical inputs the ML team's `Orchestrator` and `AgentRuntime`
implementations are validated against (PRD §77–79, master prompt §74–75).

| Fixture                 | Scenario                                             |
| ----------------------- | ---------------------------------------------------- |
| `simple_task.json`      | Single deliverable, no approval                      |
| `multi_step_task.json`  | Linear multi-step plan                               |
| `branching_task.json`   | Steps with a fan-out/fan-in dependency shape         |
| `approval_task.json`    | Flagship: reaches AWAITING_APPROVAL before send      |
| `recovery_task.json`    | Injects a verification failure to drive recovery     |
| `cancellation_task.json`| Long-running task intended to be cancelled mid-run   |
| `invalid_plan.json`     | A plan the deterministic validator must reject       |
| `impossible_task.json`  | A goal that should fail safely with no side effects  |

Consume the request body as-is against `POST /api/v1/tasks`. The `_expectation`
block documents intended control-plane outcomes and is not sent to the API.
