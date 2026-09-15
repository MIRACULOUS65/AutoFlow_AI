import type { User, Workspace } from "@/lib/types";

export const workspaces: Workspace[] = [
  {
    id: "ws_operations",
    name: "Operations",
    slug: "operations",
    description: "Reporting, reconciliation and internal operations workflows.",
    members: 12,
    createdAt: "2025-11-02T09:00:00Z",
  },
  {
    id: "ws_finance",
    name: "Finance",
    slug: "finance",
    description: "Invoice processing, compliance and financial reporting.",
    members: 8,
    createdAt: "2025-11-14T09:00:00Z",
  },
  {
    id: "ws_engineering",
    name: "Engineering",
    slug: "engineering",
    description: "Repository QA, release verification and data analysis.",
    members: 21,
    createdAt: "2025-12-01T09:00:00Z",
  },
];

export const defaultWorkspaceId = workspaces[0].id;

export const currentUser: User = {
  id: "usr_001",
  name: "Ava Mercer",
  email: "ava.mercer@example.com",
  role: "Operator",
};

export function getWorkspace(id: string): Workspace | undefined {
  return workspaces.find((w) => w.id === id);
}
