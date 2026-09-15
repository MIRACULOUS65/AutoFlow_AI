/**
 * AutoFlow AI — frontend domain model.
 *
 * These types mirror the conceptual model the eventual backend will expose, so
 * the mock repository can later be swapped for an API client without reshaping
 * the UI. Nothing here depends on any runtime or network implementation.
 */

/* ------------------------------------------------------------------ */
/* Status model                                                        */
/* ------------------------------------------------------------------ */

export type TaskStatus =
  | "QUEUED"
  | "PLANNING"
  | "VALIDATING"
  | "RUNNING"
  | "AWAITING_APPROVAL"
  | "VERIFYING"
  | "RECOVERY"
  | "COMPLETE"
  | "FAILED"
  | "CANCELLED"
  | "BLOCKED"
  | "EXPIRED";

export type ExecutionStatus = TaskStatus;

export type StepStatus =
  | "WAITING"
  | "READY"
  | "RUNNING"
  | "VERIFYING"
  | "COMPLETE"
  | "APPROVAL"
  | "FAILED"
  | "RECOVERY"
  | "SKIPPED";

export type AgentStatus = "AVAILABLE" | "BUSY" | "IDLE" | "OFFLINE";

export type VerificationState = "PASSED" | "FAILED" | "PENDING" | "NONE";

export type ApprovalStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED";

export type RecoveryPhase =
  | "RE_OBSERVING"
  | "RE_RESOLVING"
  | "RETRYING"
  | "RECOVERED"
  | "FAILED";

/* ------------------------------------------------------------------ */
/* Core entities                                                       */
/* ------------------------------------------------------------------ */

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description: string;
  members: number;
  createdAt: string;
}

export type AgentKind =
  | "planner"
  | "research"
  | "document"
  | "spreadsheet"
  | "presentation"
  | "coding"
  | "data"
  | "communication"
  | "automation"
  | "verification";

export interface AgentTool {
  id: string;
  name: string;
  description: string;
}

export interface Agent {
  id: string;
  kind: AgentKind;
  name: string;
  summary: string;
  description: string;
  status: AgentStatus;
  capabilities: string[];
  tools: AgentTool[];
  stats: {
    tasksCompleted: number;
    verificationRate: number; // 0..100
    avgDurationMs: number;
    activeRuns: number;
  };
  recentActivity: string;
}

export interface TaskStep {
  id: string;
  index: number;
  title: string;
  objective: string;
  agentId: string;
  status: StepStatus;
  verification: VerificationState;
  dependsOn: string[];
  tools: string[];
  expectedState: string;
  currentState: string;
  attempts: number;
  maxAttempts: number;
  startedAt?: string;
  completedAt?: string;
  requiresApproval?: boolean;
  approvalId?: string;
}

export interface Task {
  id: string;
  workspaceId: string;
  name: string;
  goal: string;
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
  executionId?: string;
  workflowId?: string;
  planVersion: string;
  assignedAgentId?: string;
  currentStepId?: string;
  durationMs: number;
  verification: VerificationState;
  steps: TaskStep[];
  attachments: { id: string; name: string; size: number }[];
  artifactIds: string[];
  approvalIds: string[];
  /**
   * Live execution events accumulated from the backend SSE stream in connected
   * mode. Absent in mock mode (the local simulation store supplies events).
   */
  liveEvents?: ExecutionEvent[];
}

// Canonical control-plane event types (must match the backend event stream).
export type EventType =
  | "task.created"
  | "execution.started"
  | "plan.created"
  | "plan.validated"
  | "plan.invalid"
  | "step.started"
  | "step.completed"
  | "agent.started"
  | "tool.requested"
  | "tool.started"
  | "tool.completed"
  | "observation.created"
  | "verification.started"
  | "verification.passed"
  | "verification.failed"
  | "approval.requested"
  | "approval.granted"
  | "approval.rejected"
  | "approval.expired"
  | "recovery.started"
  | "recovery.replanned"
  | "recovery.completed"
  | "artifact.created"
  | "execution.completed"
  | "execution.failed"
  | "execution.cancelled"
  // Legacy names still used by local mock data / simulation.
  | "task.planned";

export interface ExecutionEvent {
  id: string;
  at: string; // ISO timestamp
  type: EventType;
  label: string;
  agentId?: string;
  stepId?: string;
  tool?: string;
  detail?: string;
  /** Authoritative per-execution sequence (backend/connected mode only). */
  sequence?: number;
}

export interface Execution {
  id: string;
  taskId: string;
  taskName: string;
  workspaceId: string;
  status: ExecutionStatus;
  agentId: string;
  startedAt: string;
  endedAt?: string;
  durationMs: number;
  verification: VerificationState;
  planVersion: string;
  events: ExecutionEvent[];
  artifactIds: string[];
}

export type ArtifactKind =
  | "document"
  | "spreadsheet"
  | "presentation"
  | "report"
  | "image"
  | "code"
  | "log";

export interface Artifact {
  id: string;
  name: string;
  kind: ArtifactKind;
  sizeBytes: number;
  createdAt: string;
  createdBy: string; // workflow / task name
  taskId?: string;
  verification: VerificationState;
  workspaceId: string;
}

export interface EvidenceItem {
  id: string;
  label: string;
  passed: boolean;
}

export interface Approval {
  id: string;
  taskId: string;
  taskName: string;
  workspaceId: string;
  action: string;
  category: string; // e.g. "External communication"
  risk: string;
  status: ApprovalStatus;
  requestedAt: string;
  resolvedAt?: string;
  target?: string;
  attachment?: string;
  planLabel: string;
  evidence: EvidenceItem[];
}

export interface WorkflowRun {
  id: string;
  at: string;
  status: ExecutionStatus;
  durationMs: number;
  verification: VerificationState;
  version: string;
}

export interface Workflow {
  id: string;
  name: string;
  purpose: string;
  workspaceId: string;
  version: string;
  previousVersions: string[];
  lastVerifiedAt: string;
  runs: number;
  successRate: number; // 0..100
  agentIds: string[];
  stepTitles: string[];
  artifactIds: string[];
  history: WorkflowRun[];
}

export type KnowledgeType =
  | "handbook"
  | "policy"
  | "sop"
  | "procedure"
  | "guide";

export type AccessScope = "workspace" | "organization" | "restricted";

export interface KnowledgeSource {
  id: string;
  title: string;
  type: KnowledgeType;
  workspaceId: string;
  access: AccessScope;
  version: string;
  provenance: string;
  updatedAt: string;
  summary: string;
  sizeBytes: number;
}

export type FileKind =
  | "document"
  | "spreadsheet"
  | "presentation"
  | "report"
  | "image"
  | "code"
  | "log"
  | "folder";

export interface FileItem {
  id: string;
  name: string;
  kind: FileKind;
  sizeBytes: number;
  updatedAt: string;
  workspaceId: string;
  path: string;
  owner: string;
}

export type UserRole = "Operator" | "Admin" | "Viewer";

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
}
