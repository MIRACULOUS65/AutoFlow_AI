import type {
  AgentKind,
  AgentStatus,
  ApprovalStatus,
  StepStatus,
  TaskStatus,
  VerificationState,
} from "./types";

export const APP_NAME = "AutoFlow AI";
export const APP_TAGLINE = "Turn one instruction into a verified workflow.";
export const APP_VERSION =
  process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0";

/* ------------------------------------------------------------------ */
/* Status descriptors — monochrome only.                               */
/* Visual state is carried by glyph + tone (ink/border/opacity), never */
/* by color. `tone` maps to StatusBadge treatment classes.             */
/* ------------------------------------------------------------------ */

export type StatusTone = "solid" | "outline" | "muted" | "ghost" | "pulse";

export interface StatusDescriptor {
  label: string;
  glyph: string;
  description: string;
  tone: StatusTone;
}

export const TASK_STATUS: Record<TaskStatus, StatusDescriptor> = {
  QUEUED: {
    label: "Queued",
    glyph: "○",
    description: "Waiting to be planned.",
    tone: "muted",
  },
  PLANNING: {
    label: "Planning",
    glyph: "◐",
    description: "Building the execution plan.",
    tone: "outline",
  },
  VALIDATING: {
    label: "Validating",
    glyph: "◌",
    description: "Checking the plan before execution.",
    tone: "outline",
  },
  RUNNING: {
    label: "Running",
    glyph: "●",
    description: "Agents are executing the workflow.",
    tone: "pulse",
  },
  AWAITING_APPROVAL: {
    label: "Awaiting approval",
    glyph: "!",
    description: "A decision is required before continuing.",
    tone: "solid",
  },
  VERIFYING: {
    label: "Verifying",
    glyph: "◉",
    description: "Confirming the outcome is correct.",
    tone: "outline",
  },
  RECOVERY: {
    label: "Recovery",
    glyph: "↻",
    description: "Re-checking and retrying a step.",
    tone: "pulse",
  },
  COMPLETE: {
    label: "Complete",
    glyph: "✓",
    description: "Finished and verified.",
    tone: "solid",
  },
  FAILED: {
    label: "Failed",
    glyph: "×",
    description: "Could not be completed safely.",
    tone: "outline",
  },
  CANCELLED: {
    label: "Cancelled",
    glyph: "—",
    description: "Stopped before completion.",
    tone: "ghost",
  },
  BLOCKED: {
    label: "Blocked",
    glyph: "⊘",
    description: "Cannot proceed without input.",
    tone: "outline",
  },
  EXPIRED: {
    label: "Expired",
    glyph: "◍",
    description: "The window to act has passed.",
    tone: "ghost",
  },
};

export const STEP_STATUS: Record<StepStatus, StatusDescriptor> = {
  WAITING: { label: "Waiting", glyph: "○", description: "Dependencies not met.", tone: "muted" },
  READY: { label: "Ready", glyph: "◔", description: "Ready to start.", tone: "outline" },
  RUNNING: { label: "Running", glyph: "●", description: "In progress.", tone: "pulse" },
  VERIFYING: { label: "Verifying", glyph: "◉", description: "Checking output.", tone: "outline" },
  COMPLETE: { label: "Complete", glyph: "✓", description: "Done and verified.", tone: "solid" },
  APPROVAL: { label: "Approval", glyph: "!", description: "Awaiting approval.", tone: "solid" },
  FAILED: { label: "Failed", glyph: "×", description: "Step failed.", tone: "outline" },
  RECOVERY: { label: "Recovery", glyph: "↻", description: "Recovering.", tone: "pulse" },
  SKIPPED: { label: "Skipped", glyph: "–", description: "Not required.", tone: "ghost" },
};

export const APPROVAL_STATUS: Record<ApprovalStatus, StatusDescriptor> = {
  PENDING: { label: "Pending", glyph: "!", description: "Awaiting your decision.", tone: "solid" },
  APPROVED: { label: "Approved", glyph: "✓", description: "Approved.", tone: "solid" },
  REJECTED: { label: "Rejected", glyph: "×", description: "Rejected.", tone: "outline" },
  EXPIRED: { label: "Expired", glyph: "◍", description: "Window passed.", tone: "ghost" },
};

export const AGENT_STATUS: Record<AgentStatus, StatusDescriptor> = {
  AVAILABLE: { label: "Available", glyph: "○", description: "Ready for work.", tone: "outline" },
  BUSY: { label: "Busy", glyph: "●", description: "Currently executing.", tone: "pulse" },
  IDLE: { label: "Idle", glyph: "◌", description: "Standing by.", tone: "muted" },
  OFFLINE: { label: "Offline", glyph: "—", description: "Not available.", tone: "ghost" },
};

export const VERIFICATION: Record<VerificationState, StatusDescriptor> = {
  PASSED: { label: "Passed", glyph: "✓", description: "Verification passed.", tone: "solid" },
  FAILED: { label: "Failed", glyph: "×", description: "Verification failed.", tone: "outline" },
  PENDING: { label: "Pending", glyph: "◌", description: "Verification pending.", tone: "muted" },
  NONE: { label: "—", glyph: "—", description: "Not applicable.", tone: "ghost" },
};

/* ------------------------------------------------------------------ */
/* Agent kind → lucide icon name (resolved in the UI layer).           */
/* ------------------------------------------------------------------ */

export const AGENT_ICON: Record<AgentKind, string> = {
  planner: "Waypoints",
  research: "Search",
  document: "FileText",
  spreadsheet: "Table2",
  presentation: "Presentation",
  coding: "Code2",
  data: "ChartNoAxesColumn",
  communication: "Send",
  automation: "MousePointerClick",
  verification: "ShieldCheck",
};

/* ------------------------------------------------------------------ */
/* Navigation                                                          */
/* ------------------------------------------------------------------ */

export interface NavItem {
  label: string;
  href: string;
  icon: string; // lucide icon name
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { label: "Home", href: "/", icon: "LayoutDashboard" },
      { label: "Tasks", href: "/tasks", icon: "ListChecks" },
      { label: "Agents", href: "/agents", icon: "Bot" },
      { label: "Workflows", href: "/workflows", icon: "Workflow" },
      { label: "Knowledge", href: "/knowledge", icon: "BookMarked" },
      { label: "Files", href: "/files", icon: "FolderClosed" },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Approvals", href: "/approvals", icon: "BadgeCheck" },
      { label: "Executions", href: "/executions", icon: "Activity" },
    ],
  },
  {
    items: [{ label: "Settings", href: "/settings", icon: "Settings" }],
  },
];
