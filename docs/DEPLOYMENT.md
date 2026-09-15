# AutoFlow AI — Deployment

## 1. Deployment Goal

Deploy AutoFlow as a durable API-first platform with independently scalable control-plane and execution components, while keeping the desktop client thin.

## 2. Logical Production Architecture

```text
                         INTERNET / INTERNAL NETWORK
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Gateway / TLS   │
                         └────────┬────────┘
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
              ┌─────────────┐           ┌─────────────┐
              │ API Workers │           │ WebSocket / │
              │             │           │ Event API   │
              └──────┬──────┘           └──────┬──────┘
                     └────────────┬────────────┘
                                  ▼
                       ┌────────────────────┐
                       │ Orchestrator       │
                       │ Workflow Engine    │
                       └─────────┬──────────┘
                                 │
                 ┌───────────────┼────────────────┐
                 ▼               ▼                ▼
             Workers       Model Gateway       Knowledge
                 │               │                │
                 ▼               ▼                ▼
              Tools          Providers        DB / Vector
```

## 3. Core Production Components

```text
API service
Execution workers
PostgreSQL
Queue/cache
Artifact/object storage
Vector retrieval
Secret manager
Observability stack
Model provider APIs
Browser/desktop execution workers
```

## 4. Development Deployment

Single machine:

```text
Docker Compose
├── postgres
├── redis
└── optional vector store

Host processes
├── backend
├── worker
├── AI/ML harness
└── desktop
```

## 5. Staging

Staging should mirror production topology at smaller scale.

```text
TLS gateway
API workers
worker pool
PostgreSQL
queue/cache
artifact storage
vector store
observability
provider integrations
```

Use isolated credentials and test data.

## 6. Production Separation

The following concerns should be independently deployable:

```text
API/control plane
AI/model gateway
execution workers
computer-use workers
knowledge ingestion
artifact service
observability
```

This allows browser or desktop-heavy workloads to scale without scaling the public API unnecessarily.

## 7. Secrets

Secrets belong in environment injection or a dedicated secret manager.

Never commit:

```text
provider API keys
OAuth client secrets
connector passwords
JWT signing secrets
database passwords
```

The desktop receives short-lived authenticated session material, never provider master keys.

## 8. Model Providers

Providers are configured through the backend Model Gateway.

```text
Provider A
Provider B
Self-hosted API
Optional local model server
```

Switching providers should not change the workflow contract.

## 9. Database and Storage

PostgreSQL stores authoritative relational state.

Object storage holds large artifacts.

Vector storage supports semantic retrieval.

Optional graph storage supports workflow compatibility and dependencies.

## 10. Deployment Pipeline

```text
commit
 ↓
lint
 ↓
unit tests
 ↓
contract tests
 ↓
ai/ml evals
 ↓
integration tests
 ↓
build containers
 ↓
security scan
 ↓
staging deploy
 ↓
golden end-to-end suite
 ↓
production approval
 ↓
production deploy
```

## 11. Database Migrations

Migrations must be versioned and run before application code that depends on new schema versions.

Production migration rules:

```text
backup
→ migration
→ compatibility window
→ deploy application
→ verify
```

Destructive schema changes require explicit review.

## 12. Zero-Downtime Considerations

For rolling deploys:

```text
old API + new API
old workers + new workers
```

Both versions must tolerate the shared event/state contract during the migration window.

## 13. Worker Recovery

A worker crash must not erase execution state.

On restart:

```text
load persisted execution
→ identify unfinished step
→ check previous side effect / idempotency
→ resume or recover
```

## 14. Browser / Desktop Workers

Computer-use execution should run in controlled worker environments with:

```text
limited credentials
application allowlist
isolated profile/session
activity logging
kill switch
resource/time limits
```

For Windows desktop automation, the first supported target should be a controlled Windows worker or workstation rather than claiming every OS immediately.

## 15. Observability

Production must provide:

```text
structured logs
metrics
traces
execution event stream
provider health
worker health
queue depth
error rates
verification rates
recovery counts
```

## 16. Backups

Back up at minimum:

```text
PostgreSQL
workflow definitions
artifact metadata
critical object storage
configuration metadata
```

Secrets should have their own backup/recovery policy.

## 17. Disaster Recovery

The platform should document:

```text
RPO
RTO
restore procedure
worker replacement
provider outage behavior
queue recovery
artifact recovery
```

Exact targets are deployment-specific and should be measured rather than assumed.

## 18. Health Endpoints

Expose separated health checks:

```text
/liveness
/readiness
/health/models
/health/database
/health/queue
/health/storage
```

A provider outage should not necessarily make the API process itself unhealthy; it should surface as provider readiness/availability status.

## 19. Release Strategy

Prefer:

```text
staging
→ canary
→ progressive rollout
→ full rollout
```

Use rollback-compatible database changes and versioned workflow contracts.

## 20. Final Deployment Acceptance

A production deployment is accepted only when:

```text
API healthy
workers healthy
database healthy
queue healthy
artifact store healthy
model provider healthy or graceful fallback active
security checks passed
golden tasks passed
audit events present
approval flow works
reconnection works
cancellation works
```
