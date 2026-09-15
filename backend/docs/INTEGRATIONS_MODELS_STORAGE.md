# AutoFlow AI Backend — Models, Integrations, Knowledge and Storage

## 1. Purpose

This document defines the backend integration boundary for model providers, open-weight model servers, connectors, ChromaDB, PostgreSQL, object storage and workflow memory.

---

## 2. Provider-Agnostic Model Architecture

AutoFlow never stores agent logic such as “use model X” directly in task code.

Instead:

```text
AGENT CAPABILITY REQUEST
        ↓
MODEL REQUIREMENTS
        ↓
MODEL REGISTRY
        ↓
ELIGIBLE MODELS
        ↓
POLICY FILTER
        ↓
HEALTH / LATENCY / COST
        ↓
SELECT PROVIDER
        ↓
PROVIDER ADAPTER
        ↓
INFERENCE
```

---

## 3. Provider Classes

Initial provider classes:

```text
cloud_api
openai_compatible
self_hosted_vllm
self_hosted_ollama
local_runtime
embedding_server
vision_server
reranker_server
```

A generic OpenAI-compatible adapter is especially useful for self-hosted inference because vLLM currently exposes OpenAI-compatible endpoints. citeturn725794search2turn725794search8

Ollama may be supported through its own adapter or a compatibility layer; exact feature support should be tested during integration rather than assumed.

---

## 4. Open-Weight Model Strategy

The backend should support open-weight model families without embedding a specific model into application behavior.

Examples to evaluate:

```text
Gemma family
Qwen family
other approved open-weight instruct/coding/vision models
```

Current Gemma documentation describes open-weight variants across multiple deployment scales and modalities, reinforcing the need for a model registry rather than a cloud-only assumption. citeturn725794search0turn725794search7

Model selection remains an evaluation result, not a hard-coded claim.

---

## 5. Model Configuration

Environment variables should describe connection/configuration, while durable model metadata belongs in the database.

Example:

```env
MODEL_DEFAULT_PROVIDER=self_hosted
MODEL_DEFAULT_ID=...
MODEL_DEFAULT_BASE_URL=...
MODEL_DEFAULT_API_KEY=...
EMBEDDING_PROVIDER=...
EMBEDDING_MODEL=...
VISION_PROVIDER=...
VISION_MODEL=...
```

Production secrets must come from secret management.

---

## 6. Model Registry Schema

```text
model_provider
  id
  name
  type
  endpoint
  enabled

model
  id
  provider_id
  external_model_id
  display_name
  version
  capabilities
  modalities
  context_limit
  tool_support
  structured_output
  deployment_mode
  cost metadata
  health metadata
```

---

## 7. Model Health

Health is more than HTTP availability.

Check:

```text
endpoint reachable
model loaded
basic generation
structured output
tool call if supported
embedding call if relevant
vision call if relevant
latency
error rate
```

---

## 8. Model Fallback

Fallback is allowed only when:

```text
fallback capability-compatible
AND
policy-compatible
AND
context-compatible
AND
within budget
```

Fallback must be logged.

---

## 9. Gmail/Communication Connector

Communication is a high-value example because it combines drafting, attachments, approval and irreversible external side effects.

Connector capabilities:

```text
resolve sender/recipient
create draft
attach artifact
update draft
read draft
send
verify send state
```

The send tool should require approval under configured policy.

---

## 10. Files Connector

Responsibilities:

```text
resolve file
read metadata
read bytes
write bytes
rename
move
hash
```

Paths must be workspace scoped and canonicalized.

The file connector should return stable file IDs so agents do not need to reason over raw filesystem paths whenever possible.

---

## 11. Document Connector

Initial document operations:

```text
DOCX open
DOCX inspect
DOCX edit
DOCX save
DOCX render
DOCX verify
```

For “edit the same file” semantics:

```text
resolve original file_id
 ↓
read source version
 ↓
apply semantic edit
 ↓
write same logical resource
 ↓
create new content hash/version
 ↓
verify
```

Do not treat file mutation as successful until the reopened file matches expected changes.

---

## 12. Browser Connector

Capabilities:

```text
navigate
inspect page
find semantic target
click
fill field
select option
extract
upload
 download
```

The backend should store browser session IDs without storing secrets in model context.

---

## 13. Desktop Connector

Capabilities:

```text
inspect application
find semantic target
click
type
select
switch window
capture observation
```

Preferred resolution:

```text
application API
→ accessibility tree
→ DOM/semantic metadata
→ adapter
→ visual grounding
→ human
```

---

## 14. ChromaDB Role

ChromaDB is used for semantic retrieval, not authority.

```text
PostgreSQL
= identity/metadata/ACL/source of truth

ChromaDB
= semantic index
```

If ChromaDB loses an index, it should be rebuildable from authoritative source metadata and documents.

---

## 15. ChromaDB Collections

Possible collections:

```text
knowledge_chunks
workflow_memory
application_guides
```

Avoid mixing unrelated trust domains without metadata.

---

## 16. Knowledge Ingestion

```text
source registered
 ↓
fetch/read
 ↓
parse
 ↓
normalize
 ↓
chunk
 ↓
metadata
 ↓
embedding
 ↓
Chroma insert/upsert
 ↓
index status
```

Each chunk should keep provenance:

```text
source_id
document_id
version
page/section
workspace_id
permissions
content_hash
```

---

## 17. Semantic Search

Search flow:

```text
query
 ↓
ACL scope
 ↓
embedding
 ↓
vector search
 ↓
metadata filter
 ↓
rerank
 ↓
context packing
```

Results:

```json
{
  "chunk_id": "chunk_1",
  "score": 0.89,
  "source": "SOP.pdf",
  "page": 12,
  "provenance": "...",
  "scope": "operations"
}
```

---

## 18. Hallucination Controls

The backend cannot guarantee zero hallucinations, but it can make unsupported claims harder to produce.

Controls:

```text
retrieval grounding
provenance
source citations in internal context
structured outputs
verification
confidence thresholds
abstention
fact checks against source artifacts
```

For evidence-backed tasks, final results should distinguish:

```text
verified fact
inference
unknown
```

---

## 19. Memory Layers

### Session memory

Current task variables and recent observations.

### Working memory

Relevant facts retrieved for the current execution.

### Workflow memory

Verified procedures reusable across executions.

### Organization knowledge

Documents, policies, manuals and approved sources.

These layers must not be treated as one undifferentiated vector store.

---

## 20. Workflow Memory Generation

```text
completed execution
 ↓
verification summary
 ↓
semantic trace extraction
 ↓
policy check
 ↓
normalize actions
 ↓
attach provenance
 ↓
version workflow
 ↓
embed
 ↓
store in ChromaDB
 ↓
store canonical metadata in PostgreSQL
```

The semantic workflow should resemble:

```text
ResolveFile(name)
EditDocument(file_id, instructions)
SaveDocument(file_id)
ResolveSender(source_message)
CreateDraft(recipient, subject, body)
AttachArtifact(file_id)
ApproveSend()
SendEmail(draft_id)
VerifyDelivery(draft_id)
```

Not:

```text
click(812, 441)
click(917, 602)
```

The existing AI/ML specification explicitly requires verified traces to become reusable and rejects raw coordinates as canonical workflow representation. fileciteturn2file0L12-L34

---

## 21. PostgreSQL Responsibilities

Relational source of truth for:

```text
identity
tenants
workspaces
roles
permissions
tasks
plans
plan_versions
executions
steps
approvals
agents
models
tools
connectors
knowledge metadata
workflow metadata
artifacts
audit
automations
```

---

## 22. Object Storage

Store bytes of:

```text
documents
images
reports
screenshots
audio (future)
video (future)
execution artifacts
logs requiring retention
```

Object keys should contain opaque IDs, not untrusted user-provided path fragments.

---

## 23. Redis / Queue

Useful for:

```text
work queues
short-lived locks
rate limits
cache
stream fan-out
job coordination
```

Critical state remains in PostgreSQL.

---

## 24. Database/Vector Consistency

Do not assume a successful Chroma insert means the source-of-truth document was committed.

Ingestion should use states:

```text
RECEIVED
PARSED
CHUNKED
EMBEDDING
INDEXED
READY
FAILED
```

Reindexing must be resumable.

---

## 25. Deployment Profiles

### Development

```text
PostgreSQL
Redis
ChromaDB
Local object store
Local/self-hosted model server
Backend
```

### Shared development

```text
Backend
managed DB
ChromaDB
provider/self-hosted model endpoints
```

### Production

Separate model inference scaling from API scaling:

```text
Backend API replicas
Worker replicas
Model server replicas
Postgres HA
Queue/Redis
Vector service
Object storage
Observability
```

---

## 26. Backup and Recovery

Backup:

```text
Postgres
object storage
Chroma persistent data/config
secret metadata references
```

The source documents should remain authoritative enough to rebuild vector indexes.

---

## 27. Integration Test Matrix

Every connector should test:

```text
valid auth
invalid auth
expired auth
permission denial
timeout
rate limit
malformed response
partial failure
retry
idempotency
verification
```

Every model provider should test:

```text
health
basic completion
structured JSON
tool calls
streaming
timeout
provider error
fallback
```

---

## 28. End-to-End Example

```text
USER PROMPT
 ↓
TASK API
 ↓
PostgreSQL task
 ↓
Planner
 ↓
Model gateway
 ↓
Self-hosted/open-weight model OR cloud model
 ↓
Validated plan
 ↓
Document connector
 ↓
Gmail connector
 ↓
Approval service
 ↓
Execution worker
 ↓
Artifact store
 ↓
Verification
 ↓
PostgreSQL audit
 ↓
Chroma workflow memory
```

---

## 29. Integration Definition of Done

```text
[ ] one cloud/provider adapter works
[ ] one OpenAI-compatible/self-hosted adapter works
[ ] one embedding path works
[ ] ChromaDB works with ACL metadata
[ ] PostgreSQL stores authoritative state
[ ] object storage stores artifacts
[ ] Gmail or equivalent mail connector works in test environment
[ ] browser connector works in test environment
[ ] desktop connector has a controlled adapter
[ ] provider failure has a tested fallback
[ ] vector index can be rebuilt
[ ] workflow memory is provenance-aware
```
