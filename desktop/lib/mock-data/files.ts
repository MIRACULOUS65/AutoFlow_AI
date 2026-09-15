import type { FileItem } from "@/lib/types";

export const files: FileItem[] = [
  { id: "file_reports", name: "Reports", kind: "folder", sizeBytes: 0, updatedAt: "2026-09-12T17:41:24Z", workspaceId: "ws_operations", path: "/", owner: "Operations" },
  { id: "file_spreadsheets", name: "Spreadsheets", kind: "folder", sizeBytes: 0, updatedAt: "2026-09-12T16:23:44Z", workspaceId: "ws_finance", path: "/", owner: "Finance" },
  { id: "file_documents", name: "Documents", kind: "folder", sizeBytes: 0, updatedAt: "2026-09-08T09:44:00Z", workspaceId: "ws_finance", path: "/", owner: "Finance" },
  { id: "file_presentations", name: "Presentations", kind: "folder", sizeBytes: 0, updatedAt: "2026-09-10T15:31:00Z", workspaceId: "ws_operations", path: "/", owner: "Operations" },
  { id: "file_logs", name: "Logs", kind: "folder", sizeBytes: 0, updatedAt: "2026-09-11T11:02:10Z", workspaceId: "ws_engineering", path: "/", owner: "Engineering" },

  { id: "file_report_xlsx", name: "report.xlsx", kind: "spreadsheet", sizeBytes: 254_003, updatedAt: "2026-09-12T17:41:24Z", workspaceId: "ws_operations", path: "/Reports", owner: "Spreadsheet Agent" },
  { id: "file_ops_summary", name: "operations-summary.pdf", kind: "report", sizeBytes: 118_442, updatedAt: "2026-09-12T17:40:02Z", workspaceId: "ws_operations", path: "/Reports", owner: "Document Agent" },
  { id: "file_customer_report", name: "customer-report.pdf", kind: "report", sizeBytes: 204_775, updatedAt: "2026-09-04T11:50:00Z", workspaceId: "ws_operations", path: "/Reports", owner: "Document Agent" },
  { id: "file_invoice_recon", name: "invoice-reconciliation.xlsx", kind: "spreadsheet", sizeBytes: 402_881, updatedAt: "2026-09-12T16:23:44Z", workspaceId: "ws_finance", path: "/Spreadsheets", owner: "Data Analysis Agent" },
  { id: "file_monthly_analysis", name: "monthly-analysis.xlsx", kind: "spreadsheet", sizeBytes: 512_009, updatedAt: "2026-09-09T10:12:00Z", workspaceId: "ws_engineering", path: "/Spreadsheets", owner: "Data Analysis Agent" },
  { id: "file_pipeline_csv", name: "sales-pipeline.csv", kind: "report", sizeBytes: 88_120, updatedAt: "2026-09-07T14:20:00Z", workspaceId: "ws_operations", path: "/Spreadsheets", owner: "Data Analysis Agent" },
  { id: "file_compliance_pdf", name: "compliance-package.pdf", kind: "document", sizeBytes: 984_221, updatedAt: "2026-09-08T09:44:00Z", workspaceId: "ws_finance", path: "/Documents", owner: "Document Agent" },
  { id: "file_procurement_pdf", name: "procurement-review.pdf", kind: "report", sizeBytes: 341_552, updatedAt: "2026-09-05T13:15:00Z", workspaceId: "ws_finance", path: "/Documents", owner: "Document Agent" },
  { id: "file_research_md", name: "research-summary.md", kind: "document", sizeBytes: 24_880, updatedAt: "2026-09-06T16:02:00Z", workspaceId: "ws_engineering", path: "/Documents", owner: "Research Agent" },
  { id: "file_exec_brief", name: "executive-briefing.pptx", kind: "presentation", sizeBytes: 1_284_120, updatedAt: "2026-09-10T15:31:00Z", workspaceId: "ws_operations", path: "/Presentations", owner: "Presentation Agent" },
  { id: "file_qa_log", name: "repository-qa.log", kind: "log", sizeBytes: 61_233, updatedAt: "2026-09-11T11:02:10Z", workspaceId: "ws_engineering", path: "/Logs", owner: "Coding Agent" },
  { id: "file_release_patch", name: "release-checks.patch", kind: "code", sizeBytes: 12_004, updatedAt: "2026-09-03T18:00:00Z", workspaceId: "ws_engineering", path: "/Logs", owner: "Coding Agent" },
  { id: "file_ops_data", name: "operations-data.csv", kind: "report", sizeBytes: 44_120, updatedAt: "2026-09-12T17:38:00Z", workspaceId: "ws_operations", path: "/Reports", owner: "Ava Mercer" },
  { id: "file_ledger", name: "general-ledger.xlsx", kind: "spreadsheet", sizeBytes: 1_820_664, updatedAt: "2026-09-01T08:00:00Z", workspaceId: "ws_finance", path: "/Spreadsheets", owner: "Finance" },
  { id: "file_metrics", name: "product-metrics.parquet", kind: "code", sizeBytes: 4_204_991, updatedAt: "2026-09-09T09:50:00Z", workspaceId: "ws_engineering", path: "/Logs", owner: "Data Platform" },
];

export function getFile(id: string): FileItem | undefined {
  return files.find((f) => f.id === id);
}
