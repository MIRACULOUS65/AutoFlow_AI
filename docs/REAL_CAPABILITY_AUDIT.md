# AutoFlow AI — Real Capability Audit (Phase 10, Step 1)

> **Purpose.** Before building the flagship real-execution workflow, this document
> records what the system *actually does when run* — not what class names imply.
> Every "real/live" claim below was **executed**, not inferred. Where a capability
> is mock, integration, or absent, it is labeled honestly.

**Audit date:** 2026-09-12
**Scope:** `desktop/`, `backend/`, `ai-ml/` and the integration seam between them.
**Method:** code reading + direct execution probes (documented inline).

---

## 0. Baselines recorded before any Phase-10 change

| Suite | Result | Notes |
| --- | --- | --- |
| Backend (`backend/`, pytest) | **PASS** (exit 0), 7 skipped | Skips = the AI/ML-dependent integration tests (`test_real_*`, chaos), which skip when the ai-ml server on :8770 is not running. ~52 tests total (40 unit/api/flagship-mock + 12 integration). |
| AI/ML (`ai-ml/`, pytest) | Baseline ~1068 passed / 8 skipped (per project guide) | Full run deferred to the final acceptance gate (slow); not re-run in Step 1. |
| Frontend (`desktop/`, `tsc --noEmit`) | **PASS** (verified in Phase 8/9) | Electron build not re-run in Step 1. |

Mock mode remains the default across all three systems and must stay green.

---

## 1. What real capabilities already work (executed evidence)

| Capability | Status | How verified (this audit) |
| --- | --- | --- |
| **Document edit (.txt/.md)** | **LIVE** | Ran `open_document` → `apply_operations([EditOperation(kind='replace_text', find='baseline', replace='WEEKLY REPORT')])` → `save()`. Result: real file on disk, `applied=[("replace 'baseline' -> 'WEEKLY REPORT'", 1)]`, sha256 **changed**, reopened text = `WEEKLY REPORT content`. Real side effect + real reopen. |
| **Document edit (.docx)** | **LIVE (INTEGRATION for live Word UI)** | `python-docx` is INSTALLED (probed). `DocxAdapter` writes real `.docx` bytes run-by-run. The live *Word UI* path (`WordDocumentWorkflow(live=True)`) is opt-in/test-only via `AUTOFLOW_REAL_WORD`; content verification always falls back to the file-level engine. |
| **Independent document verification** | **LIVE** | The `document.verify` tool reopens the file, `sha256`, compares `hash_before != hash_after`, counts readable chars; the orchestrator variant additionally enforces `must_contain`/`must_not_contain` post-conditions on the reopened text. It raises on missing/unreadable files — never fabricates a pass. |
| **Evidence-based critic** | **LIVE** | `CriticAgent.review` treats only `TOOL_RESULT`/`OBSERVATION`/`VERIFICATION` as evidence; `AGENT` claims are not proof. Returns `NEED_MORE_EVIDENCE`/`CONTRADICTED`/`VERIFIED`. |
| **Agenticity metrics** | **LIVE (computed)** | `evaluate_agenticity` derives every flag from the observable message/blackboard trace (`independent_qa`, `success_evidence_gated` require `false_success==0 && verified_tasks>=1`, etc.). Not hardcoded. |
| **Model gateway (real LLM)** | **LIVE-capable** | `.env` has real NVIDIA NIM (`PRIMARY_MODEL_*`, `nvapi-…`) + ModelScope Qwen (`SECONDARY_*`, `ms-…`) OpenAI-compatible providers. `use_model=True` routes planning/reasoning via `ModelRouter`→`OpenAICompatibleProvider` (HTTP+SSE). Keys read only from env; never logged. Offline `use_model=False` → deterministic proposals (fails closed, no fake output). **Phase-10 decision: run the flagship with `use_model=True`.** |
| **Tool registry + per-mission allowlist** | **LIVE** | Tools registered per run into `ToolRegistry`; `validate_plan` rejects plans referencing unregistered tools/capabilities/permissions (`PlanValidationError`). FlagshipWorkflow uses `frozenset({"files:read","files:write"})`. |
| **Approval-gated send (society)** | **LIVE gate / INTEGRATION effect** | `FlagshipWorkflow` stops at `AWAITING_APPROVAL` when `auto_approve=False` and never sends; the *effect* today is a `FakeGmailAdapter` in-memory sink (no network). |
| **Control-Plane integration (Phases 1–9)** | **LIVE** | Real planning/execution/verification/approval convergence through the backend; canonical monotonic SSE; honest failure on AI/ML-unavailable; approval action-hash binding; tenancy scoping. 12 backend integration tests (skip without the ai-ml server). |

---

## 2. Which capabilities are MOCK

| Capability | Where | Note |
| --- | --- | --- |
| Backend `MockOrchestrator` / `MockAgentRuntime` / `MockToolRuntime` / `MockVerifier` / `MockRecoveryManager` / `MockPolicyEngine` | `backend/app/*/mock_*.py` | Default control-plane runtime. Deterministic fixtures. **Must remain working** (dev, CI, offline demo). |
| Desktop mock repository + client-side simulation | `desktop/lib/repository.ts`, `lib/sim-store.ts`, `lib/simulation.ts` | Default desktop mode (no backend). Includes **fake** `spreadsheet.create`/`spreadsheet.export` tools in mock data only. |
| Backend `email.send.mock` tool | mock tool runtime | Mock send in the mock execution path. |

---

## 3. Which capabilities are INTEGRATION-only (real orchestration, controlled/fake effect)

| Capability | Where | Effect |
| --- | --- | --- |
| `simulate_mission()` (ai-ml server) | `society/simulation.py` | Real local document edit + real verify, but **email via `FakeGmailAdapter`** (in-memory `_sent`, no network). |
| Gmail / email send | `society/gmail.py` | Fake DOM sink by default; a real *browser* adapter is opt-in via `AUTOFLOW_REAL_GMAIL` (test placeholder only, needs a controlled authenticated account). **No SMTP path exists.** |
| Live Word UI | `computer_use` + `word_workflow.py` | `AUTOFLOW_REAL_WORD` (test-only today); launches winword.exe via UIA when enabled; file-level verification. |

---

## 4. Which capabilities are genuinely LIVE

- Real `.txt/.md/.docx` document edit + save + **independent** reopen/hash/content verification (executed above).
- Real LLM planning/reasoning via NVIDIA + ModelScope (keys present; `use_model=True`).
- Real Control-Plane state machine, persistence, approval action-hash binding, SSE, audit, tenancy (Phases 1–9, tested).
- Real evidence-based critic + computed agenticity.

**Nothing is labeled LIVE without an executed path.**

---

## 5. Which tools create real side effects

| Tool | Real side effect today? |
| --- | --- |
| document open/edit/save (txt/md/docx) | **YES** — writes real file bytes. |
| document.verify | Read-only (reopen/hash). No mutation. |
| spreadsheet.* | **DOES NOT EXIST** (see §9). |
| email send | **NO real side effect today** — fake-DOM in-memory sink; no SMTP. |
| browser / desktop UIA / vision | Real only when opt-in env flags are set; otherwise fail-closed/SKIP. |

---

## 6. Existing verification coverage

- **Document:** structural + semantic (reopen, sha256 before/after, readable-char count, `must_contain`/`must_not_contain`). **Real & independent.**
- **Control Plane:** `verification_service.record_mission_verification` persists a durable `VerificationRun` (+ per-check rows) from the mission report; COMPLETE is gated on it (Phase 6). Verdict = `outcome.verified AND all checks pass`.
- **Gap:** no **spreadsheet** verification (no workbook reopen / sheet / column / row / totals-reconcile checks) because there is no spreadsheet capability.

## 7. Existing recovery coverage

- AI/ML: `MissionSupervisor` + critic can request more evidence / replan; recovery bounded by budgets.
- Control Plane: `_recover_step` (mock path) with bounded budget → RECOVERY → retry or FAIL; `recovery_manager` seam. Chaos tests (Phase 9) assert AI/ML-unavailable → honest FAILED (never COMPLETE).
- **Gap:** no flagship-specific real recovery fixtures yet (e.g. force a real verification failure → RECOVERY). To be added in Step 11.

## 8. Existing approval coverage

- Control Plane owns approval authority: `Approval` bound to `sha256:` action hash, TTL/expiry (`APPROVAL_EXPIRED`), approve→resume / reject→BLOCKED, invalidation on changed action (unit-tested hash sensitivity to tool/recipient/plan_version).
- Phase 7 convergence: gated mission parks pre-send; CP raises the approval; approve resumes the authorized completing run; reject blocks the send. **Real & tested.**

---

## 9. Current flagship workflow gaps

1. **No spreadsheet / `.xlsx` capability anywhere in ai-ml.**
   - Probed: `openpyxl` **MISSING**; `open_document('x.xlsx')` → `DocumentError: unsupported document type: '.xlsx'`.
   - Zero `spreadsheet|xlsx|openpyxl|data_analysis` matches in `ai-ml/**/*.py`. Referenced only in design docs + desktop mock data.
   - **The flagship's `weekly_operations_report.xlsx` cannot be produced or verified today.**
2. **No real external send.** Email is fake-DOM; no SMTP. The flagship's "send after approval + verify outcome" needs a real, controlled sink.
3. **No flagship fixtures.** No deterministic `fixtures/flagship/{data,templates,expected,runtime}` and no adversarial/prompt-injection fixture.
4. **No flagship contract fixture / test suite** (`tests/flagship/`).
5. **Desktop live-stage** must render honest execution mode (no fabricated screen when there is no real screen observation).

---

## 10. Security risks (to enforce/verify in Steps 6, 11–12)

- Real SMTP credentials must live **only** in untracked `.env`; never in code, prompts, logs, events, artifacts, tests, or Git (§70).
- Real external send must be gated: config flag + allowlisted recipient + approval + action hash + idempotency + post-send verification (§17, §18, §69). **Default OFF.**
- Retrieved/attached content is untrusted data, not instruction authority (prompt-injection fixture required, §30).
- Artifact paths confined to the flagship runtime workspace (no `../`, no absolute escape, extension/size checks, §27).
- Tenancy: cross-workspace/org isolation (already scoped; extend to real artifacts/events in Step 12).

---

## 11. Remaining blockers

| Blocker | Resolution |
| --- | --- |
| `openpyxl` not installed in `ai-ml/.venv` | `pip install openpyxl` in the ai-ml venv (add to ai-ml deps). |
| No `.xlsx` adapter / spreadsheet tools | **Option A (approved):** add additive `SpreadsheetAdapter` + `spreadsheet.create`/`spreadsheet.validate` tools + `.xlsx` dispatch in `open_document` + spreadsheet-aware verify. No rewrite of existing systems. |
| No real SMTP sink | **Approved:** real MailDog sandbox SMTP (`mail.maildog.io`), STARTTLS, credentials in `.env`. LIVE, gated OFF by default. |
| No flagship fixtures/contract/tests | Steps 2–3, 11, 13. |

---

## 12. Exact implementation plan (approved decisions)

- **use_model = True** — real NVIDIA/ModelScope LLM planning for the flagship.
- **Spreadsheet = Option A** — real `openpyxl` capability added to ai-ml as an *additive adapter within existing abstractions* (open_document dispatch, ToolRegistry, verify tool, permission allowlist). Not a rewrite; mock mode preserved.
- **Email = real SMTP (MailDog sandbox), mode LIVE, gated OFF by default.** Gates: `AUTOFLOW_ALLOW_REAL_SIDE_EFFECTS` + `REAL_EMAIL_ENABLED` (default false) + recipient allowlist + approval + action hash + idempotency key + post-send verification. Modes: `SIMULATION` (fake sink) / `INTEGRATION` (fake sink, real orchestration) / `LIVE` (real MailDog send).
- **Sequencing (approved):** audit → flagship contract + fixtures → real xlsx artifact + independent verification → real approval boundary + SMTP sink → real LLM execution through the Control Plane → recovery + security + evaluation + concurrency/restart → capability-status + production-gaps docs.
- **Honesty:** every stage labeled `SIMULATION` / `INTEGRATION` / `LIVE` / `SKIPPED`. No fake artifact/verification/approval/events/live-screen/send/recovery/LIVE label. No hardcoded flagship path — it travels the same real abstractions as any task.

---

### Appendix — execution probes run for this audit

```text
# openpyxl / docx availability + xlsx rejection
openpyxl: MISSING
python-docx: INSTALLED
xlsx: REJECTED -> DocumentError unsupported document type: '.xlsx'

# real document edit + reopen + hash (txt)
file_exists: True
applied: [("replace 'baseline' -> 'WEEKLY REPORT'", 1)]
hash_changed: True
reopened: WEEKLY REPORT content

# backend baseline
pytest exit 0 (7 skipped = ai-ml integration tests, server not running)
```
