/**
 * Map backend (snake_case) DTOs to the frontend (camelCase) domain model.
 *
 * The backend and frontend share the same conceptual model; only field naming
 * and a few enum encodings differ. Keeping the mapping here means pages and the
 * store never change when the data source flips from mock to backend.
 */
import type {
  Agent,
  Approval,
  Artifact,
  ArtifactKind,
  Execution,
  ExecutionEvent,
  KnowledgeSource,
  Task,
  TaskStep,
  VerificationState,
  Workflow,
  Workspace,
} from "@/lib/types";

/* ---- primitives ---- */

const verification = (v: string | null | undefined): VerificationState =>
  (v as VerificationState) ?? "NONE";

const ARTIFACT_KIND: Record<string, ArtifactKind> = {
  DOCX: "document",
  PDF: "report",
  XLSX: "spreadsheet",
  PPTX: "presentation",
  CSV: "report",
  JSON: "code",
  CODE: "code",
  IMAGE: "image",
  TEST_REPORT: "log",
  EMAIL_DRAFT: "document",
  MESSAGE_DRAFT: "document",
};

/* ---- entities ---- */

export function mapWorkspace(d: any): Workspace {
  return {
    id: d.id,
    name: d.name,
    slug: d.slug ?? d.name?.toLowerCase() ?? d.id,
    description: d.description ?? "",
    members: d.members ?? 0,
    createdAt: d.created_at,
  };
}

export function mapStep(d: any): TaskStep {
  return {
    id: d.id,
    index: d.index,
    title: d.title,
    objective: d.objective,
    agentId: d.agent_id,
    status: d.status,
    verification: verification(d.verification),
    dependsOn: d.depends_on ?? [],
    tools: d.tools ?? [],
    expectedState: d.expected_state ?? "",
    currentState: d.current_state ?? "",
    attempts: d.attempts ?? 0,
    maxAttempts: d.max_attempts ?? 3,
    requiresApproval: d.requires_approval,
  };
}

export function mapTask(d: any, steps: TaskStep[] = []): Task {
  return {
    id: d.id,
    workspaceId: d.workspace_id,
    name: d.name,
    goal: d.goal,
    status: d.status,
    createdAt: d.created_at,
    updatedAt: d.updated_at ?? d.created_at,
    executionId: d.execution_id ?? undefined,
    workflowId: d.workflow_id ?? undefined,
    planVersion: d.plan_version ?? "v0",
    assignedAgentId: d.assigned_agent_id ?? undefined,
    currentStepId: d.current_step_id ?? undefined,
    durationMs: d.duration_ms ?? 0,
    verification: verification(d.verification),
    steps,
    attachments: (d.attachments ?? []).map((a: any) => ({
      id: a.id,
      name: a.filename ?? a.name,
      size: a.size ?? 0,
    })),
    artifactIds: d.artifact_ids ?? [],
    approvalIds: d.approval_ids ?? [],
  };
}

export function mapEvent(d: any): ExecutionEvent {
  return {
    id: d.id,
    at: d.at,
    type: d.type,
    label: d.label ?? d.type,
    agentId: d.agent_run_id ?? undefined,
    stepId: d.step_id ?? undefined,
    tool: d.tool_call_id ?? undefined,
    detail: d.payload ? JSON.stringify(d.payload) : undefined,
    sequence: d.sequence ?? undefined,
  };
}

export function mapExecution(d: any, events: ExecutionEvent[] = []): Execution {
  return {
    id: d.id,
    taskId: d.task_id,
    taskName: d.task_name ?? "",
    workspaceId: d.workspace_id,
    status: d.status,
    agentId: d.agent_id ?? "",
    startedAt: d.started_at ?? d.created_at,
    endedAt: d.ended_at ?? undefined,
    durationMs: d.duration_ms ?? 0,
    verification: verification(d.verification),
    planVersion: `v${d.plan_version ?? 0}`,
    events,
    artifactIds: d.artifact_ids ?? [],
  };
}

export function mapArtifact(d: any): Artifact {
  return {
    id: d.id,
    name: d.name,
    kind: ARTIFACT_KIND[d.kind] ?? "document",
    sizeBytes: d.size_bytes ?? 0,
    createdAt: d.created_at,
    createdBy: d.created_by_agent ?? "AutoFlow",
    taskId: d.task_id ?? undefined,
    verification: verification(d.verification_status),
    workspaceId: d.workspace_id,
  };
}

export function mapApproval(d: any): Approval {
  return {
    id: d.id,
    taskId: d.task_id,
    taskName: d.task_name ?? "",
    workspaceId: d.workspace_id,
    action: d.action,
    category: d.category,
    risk: d.risk ?? d.risk_class ?? "",
    status: d.status,
    requestedAt: d.requested_at,
    resolvedAt: d.resolved_at ?? undefined,
    target: d.target ?? undefined,
    attachment: d.attachment ?? undefined,
    planLabel: d.plan_label ?? "",
    evidence: (d.evidence ?? []).map((e: any) => ({
      id: e.id,
      label: e.label,
      passed: e.passed,
    })),
  };
}

export function mapAgent(d: any): Agent {
  return {
    id: d.id,
    kind: (d.id?.replace("agent_", "") ?? "planner") as Agent["kind"],
    name: d.name,
    summary: d.summary ?? d.description ?? "",
    description: d.description ?? "",
    status: d.status,
    capabilities: d.capabilities ?? [],
    tools: (d.tools ?? []).map((t: any) =>
      typeof t === "string" ? { id: t, name: t, description: "" } : t,
    ),
    stats: {
      tasksCompleted: 0,
      verificationRate: 100,
      avgDurationMs: 0,
      activeRuns: 0,
    },
    recentActivity: "",
  };
}

export function mapWorkflow(d: any): Workflow {
  return {
    id: d.id,
    name: d.name,
    purpose: d.purpose,
    workspaceId: d.workspace_id,
    version: d.current_version ?? "v1",
    previousVersions: [],
    lastVerifiedAt: d.last_verified_at ?? new Date().toISOString(),
    runs: d.runs ?? 0,
    successRate: d.success_rate ?? 100,
    agentIds: d.agent_ids ?? [],
    stepTitles: d.step_titles ?? [],
    artifactIds: d.artifact_ids ?? [],
    history: [],
  };
}

export function mapKnowledge(d: any): KnowledgeSource {
  return {
    id: d.id,
    title: d.title,
    type: d.type,
    workspaceId: d.workspace_id,
    access: d.access,
    version: d.version,
    provenance: d.provenance,
    updatedAt: d.updated_at,
    summary: d.summary,
    sizeBytes: d.size_bytes ?? 0,
  };
}
