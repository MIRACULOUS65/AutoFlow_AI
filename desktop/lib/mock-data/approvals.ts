import type { Approval } from "@/lib/types";

export const approvals: Approval[] = [
  {
    id: "appr_send_finance",
    taskId: "task_ops_report",
    taskName: "Weekly Operations Report",
    workspaceId: "ws_operations",
    action: "Send email to Finance",
    category: "External communication",
    risk: "Sends a message outside the workspace.",
    status: "PENDING",
    requestedAt: "2026-09-12T17:41:27Z",
    target: "finance@example.com",
    attachment: "report.xlsx",
    planLabel: "Weekly Operations Report v3",
    evidence: [
      { id: "ev1", label: "Report verified", passed: true },
      { id: "ev2", label: "Required fields present", passed: true },
      { id: "ev3", label: "Artifact exists", passed: true },
      { id: "ev4", label: "Totals reconcile with source", passed: true },
    ],
  },
  {
    id: "appr_publish_update",
    taskId: "task_research_summary",
    taskName: "Research Summary",
    workspaceId: "ws_engineering",
    action: "Publish operations update",
    category: "Publication",
    risk: "Publishes content to a shared channel.",
    status: "PENDING",
    requestedAt: "2026-09-12T15:12:00Z",
    target: "#engineering-updates",
    attachment: "research-summary.md",
    planLabel: "Research Summary v1",
    evidence: [
      { id: "ev1", label: "Brief verified", passed: true },
      { id: "ev2", label: "Sources cited", passed: true },
      { id: "ev3", label: "No restricted content", passed: true },
    ],
  },
  {
    id: "appr_release_gate",
    taskId: "task_repo_qa",
    taskName: "Repository QA",
    workspaceId: "ws_engineering",
    action: "Approve release gate",
    category: "Release",
    risk: "Marks a release as ready to ship.",
    status: "PENDING",
    requestedAt: "2026-09-11T11:02:10Z",
    target: "release/2026.9",
    planLabel: "Repository QA v2",
    evidence: [
      { id: "ev1", label: "Unit tests passed", passed: true },
      { id: "ev2", label: "Integration tests passed", passed: true },
      { id: "ev3", label: "Release checks verified", passed: false },
    ],
  },
  {
    id: "appr_invoice_post",
    taskId: "task_invoice",
    taskName: "Invoice Reconciliation",
    workspaceId: "ws_finance",
    action: "Post reconciliation to ledger",
    category: "Financial write",
    risk: "Writes reconciled entries to the ledger.",
    status: "APPROVED",
    requestedAt: "2026-09-12T16:24:00Z",
    resolvedAt: "2026-09-12T16:25:10Z",
    target: "General Ledger",
    attachment: "invoice-reconciliation.xlsx",
    planLabel: "Invoice Reconciliation v5",
    evidence: [
      { id: "ev1", label: "Entries reconcile", passed: true },
      { id: "ev2", label: "No mismatches flagged", passed: true },
    ],
  },
  {
    id: "appr_pipeline_export",
    taskId: "task_pipeline_cleanup",
    taskName: "Sales Pipeline Cleanup",
    workspaceId: "ws_operations",
    action: "Export cleaned pipeline",
    category: "Data export",
    risk: "Exports a dataset outside the workspace.",
    status: "REJECTED",
    requestedAt: "2026-09-07T14:18:00Z",
    resolvedAt: "2026-09-07T14:19:30Z",
    target: "sales-pipeline.csv",
    planLabel: "Sales Pipeline Cleanup v1",
    evidence: [
      { id: "ev1", label: "Export scope confirmed", passed: false },
      { id: "ev2", label: "Target verified", passed: false },
    ],
  },
];

export function getApproval(id: string): Approval | undefined {
  return approvals.find((a) => a.id === id);
}

export function pendingApprovals(): Approval[] {
  return approvals.filter((a) => a.status === "PENDING");
}
