"use client";

import { create } from "zustand";
import { repository } from "@/lib/repository";
import type { Approval, ApprovalStatus, Task, TaskStatus } from "@/lib/types";

/**
 * Global UI + mock-domain store.
 *
 * This holds shared interface state (sidebar, command palette, active
 * workspace) plus a local, mutable overlay of tasks/approvals so mock
 * interactions (create task, approve/reject, run simulation) feel real without
 * a backend. Seeded from the repository on first load.
 */

interface AppState {
  // UI shell
  sidebarCollapsed: boolean;
  commandOpen: boolean;
  activeWorkspaceId: string;

  // Mutable mock domain (overlays repository seed data)
  tasks: Task[];
  approvals: Approval[];

  // actions — shell
  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;
  setCommandOpen: (v: boolean) => void;
  toggleCommand: () => void;
  setWorkspace: (id: string) => void;

  // actions — domain
  addTask: (task: Task) => void;
  updateTask: (id: string, patch: Partial<Task>) => void;
  setTaskStatus: (id: string, status: TaskStatus) => void;
  resolveApproval: (id: string, status: ApprovalStatus) => void;
  upsertApproval: (approval: Approval) => void;
  setApprovals: (approvals: Approval[]) => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  commandOpen: false,
  activeWorkspaceId: repository.defaultWorkspaceId,

  tasks: repository.tasks(),
  approvals: repository.approvals(),

  toggleSidebar: () =>
    set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  setCommandOpen: (v) => set({ commandOpen: v }),
  toggleCommand: () => set((s) => ({ commandOpen: !s.commandOpen })),
  setWorkspace: (id) => set({ activeWorkspaceId: id }),

  addTask: (task) => set((s) => ({ tasks: [task, ...s.tasks] })),
  updateTask: (id, patch) =>
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === id ? { ...t, ...patch, updatedAt: new Date().toISOString() } : t,
      ),
    })),
  setTaskStatus: (id, status) =>
    set((s) => ({
      tasks: s.tasks.map((t) =>
        t.id === id ? { ...t, status, updatedAt: new Date().toISOString() } : t,
      ),
    })),
  resolveApproval: (id, status) =>
    set((s) => ({
      approvals: s.approvals.map((a) =>
        a.id === id
          ? { ...a, status, resolvedAt: new Date().toISOString() }
          : a,
      ),
    })),
  upsertApproval: (approval) =>
    set((s) => {
      const exists = s.approvals.some((a) => a.id === approval.id);
      return {
        approvals: exists
          ? s.approvals.map((a) => (a.id === approval.id ? approval : a))
          : [approval, ...s.approvals],
      };
    }),
  setApprovals: (approvals) => set({ approvals }),
}));

/** Convenience selectors */
export const useActiveWorkspaceId = () =>
  useAppStore((s) => s.activeWorkspaceId);
