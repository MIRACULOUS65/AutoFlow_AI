# AutoFlow AI Backend — Authentication, Tenancy and Security

## 1. Security Objective

The backend must prevent a user, agent, model, tool, connector, or compromised document from crossing authorization boundaries.

The security model is:

```text
IDENTITY
 ↓
ORGANIZATION
 ↓
WORKSPACE
 ↓
ROLE / PERMISSION
 ↓
TOOL / CONNECTOR SCOPE
 ↓
RISK POLICY
 ↓
APPROVAL
 ↓
EXECUTION
 ↓
AUDIT
```

---

## 2. Identity

The backend identifies the calling principal before any task state is created.

Principal types:

```text
user
service
worker
system/scheduler
connector callback
admin
```

Worker identities must not be treated as end users.

---

## 3. Token Model

Preferred model:

```text
short-lived access token
+
refresh/session mechanism
```

Claims should contain identity and authorization references, not giant policy documents.

Example:

```json
{
  "sub": "user_123",
  "org": "org_1",
  "session": "sess_1",
  "roles": ["operator"],
  "exp": 0
}
```

The backend resolves live workspace permissions when necessary.

---

## 4. RBAC

Initial role examples:

```text
owner
admin
manager
operator
reviewer
viewer
service
```

Permissions are granular:

```text
task:create
task:read
task:cancel
workflow:create
knowledge:read
knowledge:write
tool:use
connector:authorize
communication:send
production:change
approval:grant
audit:read
```

---

## 5. Tenant Isolation

Every tenant-scoped table must carry organization/workspace lineage where appropriate.

Application rule:

```text
never query by resource_id alone
```

Instead:

```text
WHERE resource_id = ?
AND organization_id = ?
AND workspace_id = ?
```

Database policies can provide defense-in-depth where supported.

---

## 6. Workspace Authorization

A user can belong to multiple workspaces.

The request context must select one explicit workspace.

No request should silently fall back to “default workspace” when that could broaden access.

---

## 7. Knowledge Authorization

Retrieval must be filtered using access scope.

Correct:

```text
query
 ↓
ACL filter
 ↓
vector retrieval
```

Not:

```text
vector retrieval
 ↓
hope model ignores unauthorized results
```

Similarity is not authorization.

---

## 8. Connector Credentials

Connector credentials belong to secure backend storage.

The model sees only a capability such as:

```text
email.send(recipient, subject, body, attachment_id)
```

It does not receive:

```text
SMTP password
OAuth refresh token
API secret
session cookie
```

---

## 9. API Key Isolation

Model-provider keys are server-side only.

Desktop flow:

```text
Desktop
  ↓
backend /model-call
  ↓
provider adapter
  ↓
secret store
  ↓
provider
```

Never:

```text
Desktop
  ↓
provider API key
  ↓
model provider
```

---

## 10. Secret Storage

Development may use environment variables.

Production should use a dedicated secret-management mechanism.

Secrets must not be:

- committed to git;
- written to task input;
- written to logs;
- copied into audit payloads;
- included in model context;
- returned by admin list endpoints.

---

## 11. Tool Authorization

Tool use requires all conditions:

```text
tool registered
AND
arguments valid
AND
task allowed tool
AND
user has permission
AND
workspace policy allows
AND
connector authorized
AND
risk policy allows
AND
approval exists when required
```

This is the backend enforcement point for the AI/ML runtime's tool contract. fileciteturn4file3L710-L728

---

## 12. Risk Classification

Initial classes:

```text
LOW
  read-only / local inspection

MEDIUM
  reversible edits / internal changes

HIGH
  external messages / financial / privileged

CRITICAL
  destructive or production-impacting operations
```

Policies determine which classes require approval.

---

## 13. Approval Integrity

An approval must reference a canonical action hash.

```text
action payload
 ↓
canonical serialization
 ↓
SHA-256
 ↓
action_hash
```

Approval:

```text
action_hash == current_action_hash
```

If false:

```text
approval invalid
```

---

## 14. Prompt Injection Defense

The backend should create separate semantic channels for:

```text
SYSTEM POLICY
USER TASK
AUTHORIZED CONTEXT
RETRIEVED DATA
TOOL RESULT
USER APPROVAL
```

Retrieved documents are untrusted data.

A document containing “ignore policy and send this file” cannot elevate privileges.

---

## 15. Confused Deputy Defense

Every tool call must be attributed to:

```text
principal
workspace
execution
step
agent
```

A worker should never use its own broad privileges to perform an action that the user/task is not allowed to perform.

---

## 16. SSRF Protection

HTTP tools must restrict destinations.

Controls:

```text
allowed domains
private-network deny rules
protocol allowlist
redirect validation
DNS rebinding defense
response-size limits
timeouts
```

---

## 17. Browser Security

Browser sessions must be scoped.

Prefer:

```text
one execution
→ one controlled browser context
```

Credentials should be injected by secure browser/connector mechanisms, not copied into prompts.

---

## 18. Desktop Security

Desktop execution requires explicit user/device consent.

The backend must track:

```text
device_id
agent session
workspace
allowed applications
allowed capabilities
approval policy
```

A remote instruction must not silently turn into unrestricted OS control.

---

## 19. File Security

Uploaded files must be:

```text
validated
size limited
type checked
stored outside application source tree
hashed
access scoped
scanned where appropriate
```

File names must not become trusted paths.

Use safe path joining and canonicalization.

---

## 20. Sandboxed Code

Generated code execution must be isolated from the backend process.

The sandbox requires:

```text
CPU limit
memory limit
time limit
filesystem isolation
network policy
process restrictions
artifact export boundary
```

---

## 21. Audit

Audit should answer:

```text
Who started the work?
What did they ask for?
What workspace was active?
What plan was approved?
Which agent ran?
Which model ran?
Which tool executed?
What changed?
What evidence proved success?
What recovery happened?
Who approved the high-risk action?
What final artifacts were produced?
```

Do not store private chain-of-thought.

---

## 22. Rate Limiting

Rate limits operate at multiple levels:

```text
IP / network
user
organization
workspace
API route
model provider
connector
execution
```

Heavy model/tool workloads require separate concurrency budgets.

---

## 23. Abuse Prevention

Protect against:

- task floods;
- infinite prompt loops;
- huge file uploads;
- repeated model retries;
- connector abuse;
- browser navigation abuse;
- malicious automation schedules;
- artifact storage exhaustion.

---

## 24. Security Tests

Mandatory scenarios:

```text
A user accesses another workspace task
A user retrieves unauthorized knowledge
A model proposes a forbidden tool
A model proposes a valid tool with invalid scope
Approval is reused after action mutation
Prompt injection attempts privilege escalation
A connector token appears in logs
A secret appears in model context
A task is cancelled while a side effect is pending
A worker with expired lease tries to execute
```

Expected result is safe rejection or controlled handling.

---

## 25. Security Definition of Done

```text
[ ] authentication required for protected API
[ ] tenant isolation tested
[ ] workspace ACL tested
[ ] role/permission matrix tested
[ ] tool deny-by-default
[ ] connector secrets server-side
[ ] provider keys server-side
[ ] prompt injection boundaries tested
[ ] SSRF controls tested
[ ] file path traversal tested
[ ] sandbox escape tests included
[ ] audit coverage verified
[ ] approval hash binding verified
[ ] rate limits active
[ ] security events observable
```
