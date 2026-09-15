import type { Agent } from "@/lib/types";

export const agents: Agent[] = [
  {
    id: "agent_planner",
    kind: "planner",
    name: "Planner Agent",
    summary: "Plans multi-step work and sequences dependencies.",
    description:
      "Decomposes a goal into an ordered, verifiable plan. Assigns each step to a specialist agent, resolves dependencies, and defines the expected end state used for verification.",
    status: "AVAILABLE",
    capabilities: ["Goal decomposition", "Dependency resolution", "Plan validation"],
    tools: [
      { id: "plan.create", name: "plan.create", description: "Draft an execution plan." },
      { id: "plan.validate", name: "plan.validate", description: "Validate plan feasibility." },
    ],
    stats: { tasksCompleted: 214, verificationRate: 98, avgDurationMs: 4_000, activeRuns: 1 },
    recentActivity: "Created execution plan for Weekly Operations Report",
  },
  {
    id: "agent_research",
    kind: "research",
    name: "Research Agent",
    summary: "Finds and synthesizes evidence from authorized sources.",
    description:
      "Retrieves information from approved knowledge sources, checks provenance, and synthesizes concise findings with citations back to source material.",
    status: "AVAILABLE",
    capabilities: ["Source retrieval", "Provenance checks", "Synthesis"],
    tools: [
      { id: "knowledge.search", name: "knowledge.search", description: "Search approved sources." },
      { id: "knowledge.cite", name: "knowledge.cite", description: "Attach provenance." },
      { id: "web.read", name: "web.read", description: "Read an authorized page." },
    ],
    stats: { tasksCompleted: 176, verificationRate: 95, avgDurationMs: 22_000, activeRuns: 0 },
    recentActivity: "Retrieved 3 authorized sources for operations report",
  },
  {
    id: "agent_document",
    kind: "document",
    name: "Document Agent",
    summary: "Creates and validates documents.",
    description:
      "Produces structured documents from templates and validated inputs, checks required sections, and confirms formatting against workspace standards.",
    status: "IDLE",
    capabilities: ["Document generation", "Template validation", "Formatting"],
    tools: [
      { id: "doc.create", name: "doc.create", description: "Create a document." },
      { id: "doc.validate", name: "doc.validate", description: "Validate required sections." },
    ],
    stats: { tasksCompleted: 132, verificationRate: 93, avgDurationMs: 31_000, activeRuns: 0 },
    recentActivity: "Generated compliance package cover",
  },
  {
    id: "agent_spreadsheet",
    kind: "spreadsheet",
    name: "Spreadsheet Agent",
    summary: "Analyzes, transforms and generates spreadsheet deliverables.",
    description:
      "Transforms structured data into verified spreadsheets. Reconciles totals, applies workspace templates, and confirms that generated artifacts match expected schemas.",
    status: "BUSY",
    capabilities: ["Analysis", "Transformation", "Spreadsheet generation", "Reconciliation"],
    tools: [
      { id: "spreadsheet.create", name: "spreadsheet.create", description: "Create a spreadsheet." },
      { id: "spreadsheet.transform", name: "spreadsheet.transform", description: "Transform data." },
      { id: "spreadsheet.reconcile", name: "spreadsheet.reconcile", description: "Reconcile totals." },
      { id: "spreadsheet.export", name: "spreadsheet.export", description: "Export artifact." },
    ],
    stats: { tasksCompleted: 198, verificationRate: 96, avgDurationMs: 27_000, activeRuns: 1 },
    recentActivity: "Generating report.xlsx",
  },
  {
    id: "agent_presentation",
    kind: "presentation",
    name: "Presentation Agent",
    summary: "Creates presentation artifacts.",
    description:
      "Builds presentation decks from approved narratives and data, applying consistent layout and confirming that each slide maps to a verified source.",
    status: "AVAILABLE",
    capabilities: ["Deck generation", "Layout", "Narrative mapping"],
    tools: [
      { id: "deck.create", name: "deck.create", description: "Create a deck." },
      { id: "deck.export", name: "deck.export", description: "Export the deck." },
    ],
    stats: { tasksCompleted: 74, verificationRate: 91, avgDurationMs: 42_000, activeRuns: 0 },
    recentActivity: "Prepared executive briefing deck",
  },
  {
    id: "agent_coding",
    kind: "coding",
    name: "Coding Agent",
    summary: "Writes and tests code.",
    description:
      "Implements and reviews code changes against acceptance criteria, runs test suites, and reports verification outcomes without merging without approval.",
    status: "IDLE",
    capabilities: ["Implementation", "Testing", "Code review"],
    tools: [
      { id: "code.edit", name: "code.edit", description: "Apply a code change." },
      { id: "code.test", name: "code.test", description: "Run tests." },
      { id: "code.review", name: "code.review", description: "Review a change." },
    ],
    stats: { tasksCompleted: 89, verificationRate: 90, avgDurationMs: 51_000, activeRuns: 0 },
    recentActivity: "Ran repository QA suite",
  },
  {
    id: "agent_data",
    kind: "data",
    name: "Data Analysis Agent",
    summary: "Analyzes structured data.",
    description:
      "Runs analysis over structured datasets, validates assumptions, and produces reconciled figures that downstream agents can rely on.",
    status: "AVAILABLE",
    capabilities: ["Analysis", "Validation", "Aggregation"],
    tools: [
      { id: "data.query", name: "data.query", description: "Query a dataset." },
      { id: "data.validate", name: "data.validate", description: "Validate assumptions." },
      { id: "data.aggregate", name: "data.aggregate", description: "Aggregate figures." },
    ],
    stats: { tasksCompleted: 151, verificationRate: 97, avgDurationMs: 34_000, activeRuns: 0 },
    recentActivity: "Analyzed monthly figures for invoice report",
  },
  {
    id: "agent_communication",
    kind: "communication",
    name: "Communication Agent",
    summary: "Creates communications and prepares external actions.",
    description:
      "Drafts communications from verified artifacts. External actions always route through an approval checkpoint before anything is sent.",
    status: "AVAILABLE",
    capabilities: ["Drafting", "Recipient resolution", "Approval routing"],
    tools: [
      { id: "email.draft", name: "email.draft", description: "Draft an email." },
      { id: "email.send", name: "email.send", description: "Send (requires approval)." },
    ],
    stats: { tasksCompleted: 118, verificationRate: 94, avgDurationMs: 12_000, activeRuns: 0 },
    recentActivity: "Prepared email draft for finance",
  },
  {
    id: "agent_automation",
    kind: "automation",
    name: "Computer Automation Agent",
    summary: "Operates supported applications.",
    description:
      "Performs guided actions inside supported applications, observing state before and after each step and pausing for recovery when the target cannot be verified.",
    status: "OFFLINE",
    capabilities: ["Application control", "State observation", "Guarded actions"],
    tools: [
      { id: "app.observe", name: "app.observe", description: "Observe application state." },
      { id: "app.act", name: "app.act", description: "Perform a guarded action." },
    ],
    stats: { tasksCompleted: 63, verificationRate: 88, avgDurationMs: 46_000, activeRuns: 0 },
    recentActivity: "Standing by",
  },
  {
    id: "agent_verification",
    kind: "verification",
    name: "Verification Agent",
    summary: "Validates outputs and outcomes.",
    description:
      "Independently checks that produced artifacts and end states match expectations. Verification must pass before an approval or final action can proceed.",
    status: "AVAILABLE",
    capabilities: ["Outcome verification", "Field checks", "Reconciliation"],
    tools: [
      { id: "verify.fields", name: "verify.fields", description: "Check required fields." },
      { id: "verify.reconcile", name: "verify.reconcile", description: "Reconcile totals." },
      { id: "verify.artifact", name: "verify.artifact", description: "Confirm artifact exists." },
    ],
    stats: { tasksCompleted: 203, verificationRate: 99, avgDurationMs: 9_000, activeRuns: 0 },
    recentActivity: "Verified report totals reconcile",
  },
];

export function getAgent(id: string): Agent | undefined {
  return agents.find((a) => a.id === id);
}

export function agentName(id?: string): string {
  if (!id) return "—";
  return getAgent(id)?.name ?? id;
}
