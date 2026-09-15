/**
 * Backend-backed repository.
 *
 * Async mirror of the local mock `repository`. It fetches from the control
 * plane and maps responses into the frontend domain model, so a future
 * migration can swap the data source behind the existing seam without touching
 * pages. Includes command methods (create/approve/reject/cancel) the mock
 * repository does not need.
 */
import { api, type Paginated } from "@/lib/api/client";
import {
  mapAgent,
  mapApproval,
  mapArtifact,
  mapEvent,
  mapExecution,
  mapKnowledge,
  mapStep,
  mapTask,
  mapWorkflow,
  mapWorkspace,
} from "@/lib/api/mappers";
import type {
  Agent,
  Approval,
  Artifact,
  Execution,
  ExecutionEvent,
  FileItem,
  KnowledgeSource,
  Task,
  Workflow,
  Workspace,
} from "@/lib/types";

const wsQuery = (workspaceId?: string) =>
  workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";

export const backendRepository = {
  // Workspaces
  async workspaces(): Promise<Workspace[]> {
    const rows = await api.get<any[]>("/workspaces");
    return rows.map(mapWorkspace);
  },
  async workspace(id: string): Promise<Workspace | undefined> {
    try {
      return mapWorkspace(await api.get<any>(`/workspaces/${id}`));
    } catch {
      return undefined;
    }
  },

  // Tasks
  async tasks(workspaceId?: string): Promise<Task[]> {
    const page = await api.get<Paginated<any>>(`/tasks${wsQuery(workspaceId)}`);
    return page.items.map((t) => mapTask(t));
  },
  async task(id: string): Promise<Task | undefined> {
    try {
      const d = await api.get<any>(`/tasks/${id}`);
      const steps = d.execution_id
        ? (await api.get<any[]>(`/executions/${d.execution_id}/steps`)).map(mapStep)
        : [];
      return mapTask(d, steps);
    } catch {
      return undefined;
    }
  },

  // Executions
  async executions(workspaceId?: string): Promise<Execution[]> {
    const page = await api.get<Paginated<any>>(`/executions${wsQuery(workspaceId)}`);
    return page.items.map((e) => mapExecution(e));
  },
  async execution(id: string): Promise<Execution | undefined> {
    try {
      const d = await api.get<any>(`/executions/${id}`);
      const events = (await api.get<any[]>(`/executions/${id}/events?after=0`)).map(
        mapEvent,
      );
      return mapExecution(d, events);
    } catch {
      return undefined;
    }
  },

  // Approvals
  async approvals(workspaceId?: string): Promise<Approval[]> {
    const page = await api.get<Paginated<any>>(`/approvals${wsQuery(workspaceId)}`);
    return page.items.map(mapApproval);
  },
  async approval(id: string): Promise<Approval | undefined> {
    try {
      return mapApproval(await api.get<any>(`/approvals/${id}`));
    } catch {
      return undefined;
    }
  },

  // Artifacts
  async artifacts(workspaceId?: string): Promise<Artifact[]> {
    const page = await api.get<Paginated<any>>(`/artifacts${wsQuery(workspaceId)}`);
    return page.items.map(mapArtifact);
  },

  // Agents
  async agents(): Promise<Agent[]> {
    return (await api.get<any[]>("/agents")).map(mapAgent);
  },
  async agent(id: string): Promise<Agent | undefined> {
    try {
      return mapAgent(await api.get<any>(`/agents/${id}`));
    } catch {
      return undefined;
    }
  },

  // Workflows
  async workflows(workspaceId?: string): Promise<Workflow[]> {
    const page = await api.get<Paginated<any>>(`/workflows${wsQuery(workspaceId)}`);
    return page.items.map(mapWorkflow);
  },

  // Knowledge
  async knowledge(workspaceId?: string): Promise<KnowledgeSource[]> {
    const page = await api.get<Paginated<any>>(
      `/knowledge/sources${wsQuery(workspaceId)}`,
    );
    return page.items.map(mapKnowledge);
  },

  // Files — the backend models real deliverables as artifacts; the Files page
  // presents them as FileItems. This maps real artifacts (no folders).
  async files(workspaceId?: string): Promise<FileItem[]> {
    const page = await api.get<Paginated<any>>(`/artifacts${wsQuery(workspaceId)}`);
    return page.items.map((a) => {
      const art = mapArtifact(a);
      const file: FileItem = {
        id: art.id,
        name: art.name,
        kind: (art.kind as unknown as FileItem["kind"]) ?? "document",
        sizeBytes: art.sizeBytes,
        updatedAt: art.createdAt,
        workspaceId: art.workspaceId,
        path: "/",
        owner: art.createdBy,
      };
      return file;
    });
  },

  /* ---- commands ---- */

  async createTask(input: {
    workspaceId: string;
    goal: string;
    idempotencyKey?: string;
    clientMetadata?: Record<string, unknown>;
  }): Promise<{ taskId: string; executionId: string; status: string }> {
    const headers = input.idempotencyKey
      ? { "Idempotency-Key": input.idempotencyKey }
      : undefined;
    const payload: Record<string, unknown> = {
      workspace_id: input.workspaceId,
      goal: input.goal,
    };
    if (input.clientMetadata && Object.keys(input.clientMetadata).length > 0) {
      payload.client_metadata = input.clientMetadata;
    }
    const d = await api.post<any>("/tasks", payload, headers);
    return { taskId: d.task_id, executionId: d.execution_id, status: d.status };
  },

  async approve(approvalId: string, reason?: string): Promise<Approval> {
    return mapApproval(await api.post<any>(`/approvals/${approvalId}/approve`, { reason }));
  },
  async reject(approvalId: string, reason?: string): Promise<Approval> {
    return mapApproval(await api.post<any>(`/approvals/${approvalId}/reject`, { reason }));
  },
  async cancelTask(taskId: string): Promise<void> {
    await api.post(`/tasks/${taskId}/cancel`);
  },

  /** Reconnect-safe event fetch (?after=<sequence>). */
  async events(executionId: string, after = 0): Promise<ExecutionEvent[]> {
    return (
      await api.get<any[]>(`/executions/${executionId}/events?after=${after}`)
    ).map(mapEvent);
  },
};

export type BackendRepository = typeof backendRepository;
