# AutoFlow AI Backend — API Specification

## 1. API Strategy

Base path:

```text
/api/v1
```

Transport:

```text
HTTPS + JSON
WebSocket or SSE for execution streaming
multipart/form-data for file upload where appropriate
```

API principles:

- asynchronous for long-running operations;
- idempotent where side effects could duplicate;
- explicit versioning;
- stable resource identifiers;
- structured errors;
- pagination;
- request IDs;
- optimistic concurrency for mutable control-plane resources.

---

## 2. Authentication

```http
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

Example login:

```json
{
  "email": "user@example.com",
  "password": "..."
}
```

The API must return tokens/session metadata without exposing provider keys.

---

## 3. Organizations

```http
GET  /organizations
GET  /organizations/{organization_id}
POST /organizations
```

User permissions determine visible organizations.

---

## 4. Workspaces

```http
GET  /workspaces
GET  /workspaces/{workspace_id}
POST /workspaces
PATCH /workspaces/{workspace_id}
```

Workspace response:

```json
{
  "id": "ws_123",
  "organization_id": "org_1",
  "name": "Operations",
  "policy_profile": "standard",
  "capabilities": ["documents", "email", "browser"],
  "created_at": "..."
}
```

---

## 5. Task Creation

```http
POST /api/v1/tasks
Idempotency-Key: request-123
```

Request:

```json
{
  "workspace_id": "ws_123",
  "input": {
    "text": "Edit the attached Word document and email it to the original sender after I approve."
  },
  "attachments": [
    {
      "file_id": "file_abc"
    }
  ],
  "constraints": {
    "deadline": null,
    "read_only": false
  },
  "execution_mode": "autonomous_with_approval"
}
```

Response:

```json
{
  "task_id": "task_123",
  "execution_id": "exec_123",
  "state": "QUEUED",
  "created_at": "..."
}
```

---

## 6. Task Read

```http
GET /api/v1/tasks/{task_id}
GET /api/v1/tasks/{task_id}/events
GET /api/v1/tasks/{task_id}/artifacts
```

Task detail should include:

```text
goal
state
current step
execution
plan summary
approval status
artifacts
created/updated timestamps
```

Do not include private chain-of-thought.

---

## 7. Task Controls

```http
POST /api/v1/tasks/{task_id}/pause
POST /api/v1/tasks/{task_id}/resume
POST /api/v1/tasks/{task_id}/cancel
POST /api/v1/tasks/{task_id}/retry
```

Controls must be authorization checked.

---

## 8. Plan APIs

```http
POST /api/v1/tasks/{task_id}/plan
GET  /api/v1/tasks/{task_id}/plan
GET  /api/v1/plans/{plan_id}
GET  /api/v1/plans/{plan_id}/versions
POST /api/v1/plans/{plan_id}/validate
```

Plan object:

```json
{
  "plan_id": "plan_123",
  "task_id": "task_123",
  "version": 3,
  "hash": "sha256:...",
  "state": "validated",
  "steps": []
}
```

---

## 9. Approval APIs

```http
GET  /api/v1/approvals
GET  /api/v1/approvals/{approval_id}
POST /api/v1/approvals/{approval_id}/approve
POST /api/v1/approvals/{approval_id}/reject
```

Approval response:

```json
{
  "approval_id": "apr_123",
  "execution_id": "exec_123",
  "step_id": "step_7",
  "risk_class": "high",
  "action_hash": "sha256:...",
  "status": "pending",
  "summary": "Send email to external recipient",
  "evidence": ["artifact://..."],
  "expires_at": "..."
}
```

---

## 10. Execution APIs

```http
GET  /api/v1/executions/{execution_id}
GET  /api/v1/executions/{execution_id}/steps
GET  /api/v1/executions/{execution_id}/events
POST /api/v1/executions/{execution_id}/pause
POST /api/v1/executions/{execution_id}/resume
POST /api/v1/executions/{execution_id}/cancel
```

Stream:

```text
GET /api/v1/executions/{execution_id}/stream
```

The server may use SSE or WebSocket. The event payload remains the same normalized event schema.

---

## 11. Example Event Stream

```json
{
  "event_id": "evt_123",
  "type": "step.status.changed",
  "execution_id": "exec_123",
  "step_id": "step_3",
  "status": "awaiting_approval",
  "timestamp": "...",
  "data": {
    "agent": "communication-agent",
    "risk": "high"
  }
}
```

Event types:

```text
task.created
task.normalized
plan.created
plan.validated
approval.requested
approval.granted
approval.rejected
execution.started
step.started
agent.started
model.call.started
model.call.completed
tool.requested
tool.started
tool.completed
observation.created
verification.started
verification.passed
verification.failed
recovery.started
recovery.replanned
artifact.created
execution.paused
execution.resumed
execution.completed
execution.failed
execution.cancelled
```

---

## 12. Agent Registry API

```http
GET  /api/v1/agents
GET  /api/v1/agents/{agent_id}
POST /api/v1/agents
PATCH /api/v1/agents/{agent_id}
```

Agent definition:

```json
{
  "id": "document-agent",
  "capabilities": ["document_editing", "document_generation"],
  "allowed_tools": ["files.read", "docx.edit", "docx.save"],
  "model_policy": {
    "required_capabilities": ["reasoning", "structured_output"]
  }
}
```

---

## 13. Model Registry API

```http
GET  /api/v1/models
GET  /api/v1/models/{model_id}
POST /api/v1/models
POST /api/v1/models/{model_id}/health-check
```

Model registration must support self-hosted endpoints:

```json
{
  "provider_type": "self_hosted_openai_compatible",
  "endpoint": "http://model-server:8000/v1",
  "model_name": "<deployment-model>",
  "capabilities": [
    "reasoning",
    "structured_output",
    "tool_calling"
  ]
}
```

Never return stored credentials in the response.

---

## 14. Tools API

```http
GET /api/v1/tools
GET /api/v1/tools/{tool_id}
```

The backend may keep tool registration admin-only while exposing available-tool summaries to task planners.

---

## 15. Connectors API

```http
GET  /api/v1/connectors
POST /api/v1/connectors
GET  /api/v1/connectors/{connector_id}
POST /api/v1/connectors/{connector_id}/health
POST /api/v1/connectors/{connector_id}/authorize
POST /api/v1/connectors/{connector_id}/revoke
```

Sensitive authorization values must be stored in secure server-side storage.

---

## 16. Knowledge APIs

```http
POST /api/v1/knowledge/sources
POST /api/v1/knowledge/index
GET  /api/v1/knowledge/search
GET  /api/v1/knowledge/items/{item_id}
DELETE /api/v1/knowledge/items/{item_id}
```

Search request:

```json
{
  "workspace_id": "ws_123",
  "query": "approved invoice process",
  "limit": 8,
  "filters": {
    "content_type": ["pdf", "docx"]
  }
}
```

The backend applies authorization before vector results are returned.

---

## 17. Workflow Memory APIs

```http
GET  /api/v1/workflows
GET  /api/v1/workflows/{workflow_id}
POST /api/v1/workflows/{workflow_id}/activate
POST /api/v1/workflows/{workflow_id}/archive
POST /api/v1/workflows/from-execution/{execution_id}
```

Workflow memory is generated from verified execution data, not raw model text.

---

## 18. Artifact APIs

```http
POST /api/v1/artifacts/upload
GET  /api/v1/artifacts/{artifact_id}
GET  /api/v1/artifacts/{artifact_id}/content
GET  /api/v1/artifacts/{artifact_id}/download
POST /api/v1/artifacts/{artifact_id}/verify
```

Artifact response:

```json
{
  "artifact_id": "art_123",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "content_hash": "sha256:...",
  "verification_status": "passed",
  "source_execution_id": "exec_123"
}
```

---

## 19. Automations APIs

```http
GET  /api/v1/automations
POST /api/v1/automations
GET  /api/v1/automations/{automation_id}
PATCH /api/v1/automations/{automation_id}
POST /api/v1/automations/{automation_id}/enable
POST /api/v1/automations/{automation_id}/disable
POST /api/v1/automations/{automation_id}/run-now
```

Automation request:

```json
{
  "workspace_id": "ws_123",
  "name": "Weekly report",
  "schedule": "RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0",
  "timezone": "Asia/Kolkata",
  "input_template": "Prepare this week's operations report and draft the finance email.",
  "execution_policy": "approval_required_for_send"
}
```

---

## 20. Audit APIs

```http
GET /api/v1/audit/events
GET /api/v1/audit/executions/{execution_id}
```

Audit endpoints must be more restrictive than normal task endpoints.

---

## 21. Error Contract

```json
{
  "error": {
    "code": "approval_required",
    "message": "Execution is paused pending approval.",
    "request_id": "req_123",
    "details": {
      "approval_id": "apr_1"
    }
  }
}
```

Canonical error classes:

```text
validation_error
authentication_error
authorization_error
not_found
conflict
rate_limited
approval_required
provider_unavailable
tool_unavailable
execution_failed
verification_failed
policy_blocked
internal_error
```

---

## 22. Pagination

Cursor pagination is preferred for event-heavy resources.

```http
GET /api/v1/executions?cursor=...
```

Response:

```json
{
  "items": [],
  "next_cursor": "..."
}
```

---

## 23. Idempotency

Use `Idempotency-Key` for task creation and any endpoint that may cause an external side effect.

The server stores:

```text
idempotency_key
principal_id
route
request_hash
response_hash
status
created_at
```

A reused key with a different request body must return conflict.

---

## 24. Optimistic Concurrency

Mutable control-plane objects may expose:

```text
version
ETag
If-Match
```

Approval objects and active automation definitions should reject stale mutations.

---

## 25. API Security

Every endpoint must declare:

```text
auth requirement
required role/permission
workspace requirement
rate limit class
idempotency requirement
sensitive fields policy
```

---

## 26. API Acceptance Workflow

The canonical black-box API test is:

```text
POST /tasks
 ↓
GET /tasks/{id}
 ↓
GET /plan
 ↓
GET /approvals
 ↓
POST /approve
 ↓
GET /execution stream
 ↓
GET /artifacts
 ↓
GET /task final state
 ↓
GET /audit
```

All steps must correspond to persisted backend state.
