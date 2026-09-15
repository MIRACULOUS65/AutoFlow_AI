import type { Workflow } from "@/lib/types";

export const workflows: Workflow[] = [
  {
    id: "wf_weekly_ops",
    name: "Weekly Operations Report",
    purpose:
      "Retrieve approved operations data, generate a verified report, and route it to finance for approval before sending.",
    workspaceId: "ws_operations",
    version: "v3",
    previousVersions: ["v2", "v1"],
    lastVerifiedAt: "2026-09-12T17:41:26Z",
    runs: 18,
    successRate: 94,
    agentIds: ["agent_research", "agent_data", "agent_spreadsheet", "agent_verification", "agent_communication"],
    stepTitles: ["Retrieve data", "Analyze data", "Create report", "Validate data", "Prepare email", "Approval", "Send"],
    artifactIds: ["art_report_xlsx", "art_ops_summary_pdf"],
    history: [
      { id: "wr_ops_1", at: "2026-09-12T17:41:26Z", status: "AWAITING_APPROVAL", durationMs: 132_000, verification: "PASSED", version: "v3" },
      { id: "wr_ops_2", at: "2026-09-05T17:38:00Z", status: "COMPLETE", durationMs: 128_000, verification: "PASSED", version: "v3" },
      { id: "wr_ops_3", at: "2026-08-29T17:40:00Z", status: "COMPLETE", durationMs: 141_000, verification: "PASSED", version: "v2" },
    ],
  },
  {
    id: "wf_invoice",
    name: "Invoice Processing",
    purpose:
      "Reconcile invoices against the ledger, flag mismatches, and post approved entries.",
    workspaceId: "ws_finance",
    version: "v5",
    previousVersions: ["v4", "v3", "v2", "v1"],
    lastVerifiedAt: "2026-09-12T16:26:40Z",
    runs: 41,
    successRate: 97,
    agentIds: ["agent_data", "agent_verification"],
    stepTitles: ["Load ledger", "Load invoices", "Reconcile entries", "Generate reconciliation", "Approval"],
    artifactIds: ["art_invoice_recon_xlsx"],
    history: [
      { id: "wr_inv_1", at: "2026-09-12T16:26:40Z", status: "COMPLETE", durationMs: 248_000, verification: "PASSED", version: "v5" },
      { id: "wr_inv_2", at: "2026-08-12T16:20:00Z", status: "COMPLETE", durationMs: 262_000, verification: "PASSED", version: "v4" },
    ],
  },
  {
    id: "wf_repo_qa",
    name: "Repository QA",
    purpose:
      "Run unit and integration suites and verify the release gate against a target environment.",
    workspaceId: "ws_engineering",
    version: "v2",
    previousVersions: ["v1"],
    lastVerifiedAt: "2026-09-08T11:00:00Z",
    runs: 12,
    successRate: 91,
    agentIds: ["agent_coding", "agent_verification"],
    stepTitles: ["Checkout repository", "Run unit tests", "Run integration tests", "Verify release checks"],
    artifactIds: ["art_qa_log"],
    history: [
      { id: "wr_qa_1", at: "2026-09-11T11:02:10Z", status: "RECOVERY", durationMs: 271_000, verification: "PENDING", version: "v2" },
      { id: "wr_qa_2", at: "2026-09-08T11:00:00Z", status: "COMPLETE", durationMs: 254_000, verification: "PASSED", version: "v2" },
    ],
  },
  {
    id: "wf_monthly_data",
    name: "Monthly Data Analysis",
    purpose:
      "Analyze monthly product metrics, flag anomalies, and produce a verified report.",
    workspaceId: "ws_engineering",
    version: "v4",
    previousVersions: ["v3", "v2", "v1"],
    lastVerifiedAt: "2026-09-09T10:12:00Z",
    runs: 26,
    successRate: 95,
    agentIds: ["agent_data", "agent_verification"],
    stepTitles: ["Load metrics", "Run analysis", "Flag anomalies", "Generate report"],
    artifactIds: ["art_monthly_data_xlsx"],
    history: [
      { id: "wr_mda_1", at: "2026-09-09T10:12:00Z", status: "COMPLETE", durationMs: 1_320_000, verification: "PASSED", version: "v4" },
    ],
  },
  {
    id: "wf_compliance",
    name: "Compliance Package",
    purpose:
      "Assemble the quarterly compliance package from approved documents and verify completeness.",
    workspaceId: "ws_finance",
    version: "v2",
    previousVersions: ["v1"],
    lastVerifiedAt: "2026-08-30T09:44:00Z",
    runs: 6,
    successRate: 100,
    agentIds: ["agent_document", "agent_verification"],
    stepTitles: ["Collect documents", "Assemble package", "Verify"],
    artifactIds: ["art_compliance_pdf"],
    history: [
      { id: "wr_comp_1", at: "2026-08-30T09:44:00Z", status: "COMPLETE", durationMs: 720_000, verification: "PASSED", version: "v2" },
    ],
  },
];

export function getWorkflow(id: string): Workflow | undefined {
  return workflows.find((w) => w.id === id);
}
