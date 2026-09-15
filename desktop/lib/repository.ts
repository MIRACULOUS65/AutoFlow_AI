/**
 * Frontend repository layer.
 *
 * The UI depends on this module, never on the raw mock files. Today it reads
 * from local mock data; later it can be replaced with an API client that
 * implements the same interface without touching any component.
 */
import { agents, getAgent } from "@/lib/mock-data/agents";
import { approvals, getApproval } from "@/lib/mock-data/approvals";
import { artifacts, getArtifact } from "@/lib/mock-data/artifacts";
import { executions, getExecution } from "@/lib/mock-data/executions";
import { files, getFile } from "@/lib/mock-data/files";
import { getKnowledgeSource, knowledgeSources } from "@/lib/mock-data/knowledge";
import { getTask, tasks } from "@/lib/mock-data/tasks";
import { getWorkflow, workflows } from "@/lib/mock-data/workflows";
import {
  currentUser,
  defaultWorkspaceId,
  getWorkspace,
  workspaces,
} from "@/lib/mock-data/workspaces";
import type {
  Agent,
  Approval,
  Artifact,
  Execution,
  FileItem,
  KnowledgeSource,
  Task,
  Workflow,
  Workspace,
} from "@/lib/types";

const byWorkspace = <T extends { workspaceId: string }>(
  items: T[],
  workspaceId?: string,
): T[] => (workspaceId ? items.filter((i) => i.workspaceId === workspaceId) : items);

export const repository = {
  // Workspaces & identity
  workspaces: (): Workspace[] => workspaces,
  workspace: (id: string): Workspace | undefined => getWorkspace(id),
  defaultWorkspaceId,
  currentUser,

  // Tasks
  tasks: (workspaceId?: string): Task[] => byWorkspace(tasks, workspaceId),
  task: (id: string): Task | undefined => getTask(id),

  // Agents (not workspace-scoped)
  agents: (): Agent[] => agents,
  agent: (id: string): Agent | undefined => getAgent(id),

  // Workflows
  workflows: (workspaceId?: string): Workflow[] => byWorkspace(workflows, workspaceId),
  workflow: (id: string): Workflow | undefined => getWorkflow(id),

  // Executions
  executions: (workspaceId?: string): Execution[] =>
    byWorkspace(executions, workspaceId),
  execution: (id: string): Execution | undefined => getExecution(id),

  // Approvals
  approvals: (workspaceId?: string): Approval[] => byWorkspace(approvals, workspaceId),
  approval: (id: string): Approval | undefined => getApproval(id),

  // Artifacts
  artifacts: (workspaceId?: string): Artifact[] => byWorkspace(artifacts, workspaceId),
  artifact: (id: string): Artifact | undefined => getArtifact(id),

  // Knowledge
  knowledge: (workspaceId?: string): KnowledgeSource[] =>
    byWorkspace(knowledgeSources, workspaceId),
  knowledgeSource: (id: string): KnowledgeSource | undefined =>
    getKnowledgeSource(id),

  // Files
  files: (workspaceId?: string): FileItem[] => byWorkspace(files, workspaceId),
  file: (id: string): FileItem | undefined => getFile(id),
};

export type Repository = typeof repository;
