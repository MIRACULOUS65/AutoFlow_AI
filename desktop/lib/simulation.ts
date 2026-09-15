import type {
  ExecutionEvent,
  Task,
  TaskStatus,
  TaskStep,
} from "@/lib/types";

/**
 * Frontend-only execution simulation.
 *
 * Given a goal, this builds a plausible plan and returns a scripted sequence of
 * state transitions that the UI can play back on a timer. No backend, no real
 * agents — every transition is local. This mirrors the conceptual event model
 * the real backend will later emit so the UI does not need to change.
 */

export interface SimStepTemplate {
  title: string;
  objective: string;
  agentId: string;
  tools: string[];
  expectedState: string;
  runningState: string;
  doneState: string;
  requiresApproval?: boolean;
}

/** A default plan used for new tasks created via the composer. */
const DEFAULT_PLAN: SimStepTemplate[] = [
  {
    title: "Understand goal",
    objective: "Interpret the goal and identify the required outcome.",
    agentId: "agent_planner",
    tools: ["plan.create"],
    expectedState: "Goal understood and scoped.",
    runningState: "Interpreting the goal…",
    doneState: "Goal understood.",
  },
  {
    title: "Retrieve data",
    objective: "Retrieve the information required to complete the goal.",
    agentId: "agent_research",
    tools: ["knowledge.search"],
    expectedState: "Required sources retrieved.",
    runningState: "Retrieving authorized sources…",
    doneState: "Sources retrieved.",
  },
  {
    title: "Produce deliverable",
    objective: "Generate the primary deliverable.",
    agentId: "agent_spreadsheet",
    tools: ["spreadsheet.create"],
    expectedState: "Deliverable generated.",
    runningState: "Generating deliverable…",
    doneState: "Deliverable generated.",
  },
  {
    title: "Verify",
    objective: "Independently verify the deliverable.",
    agentId: "agent_verification",
    tools: ["verify.artifact", "verify.fields"],
    expectedState: "Deliverable verified.",
    runningState: "Verifying deliverable…",
    doneState: "Verification passed.",
  },
  {
    title: "Approval",
    objective: "Request approval before any external action.",
    agentId: "agent_communication",
    tools: [],
    expectedState: "Human approval recorded.",
    runningState: "Awaiting approval…",
    doneState: "Approved.",
    requiresApproval: true,
  },
];

let counter = 1000;
function nextId(prefix: string): string {
  counter += 1;
  return `${prefix}_${Date.now().toString(36)}${counter}`;
}

/** Build a fresh Task in QUEUED state from a goal + workspace. */
export function createTaskFromGoal(
  goal: string,
  workspaceId: string,
  name?: string,
): Task {
  const id = nextId("task");
  const executionId = nextId("exec");
  const now = new Date().toISOString();

  const steps: TaskStep[] = DEFAULT_PLAN.map((t, i) => ({
    id: `${id}_s${i + 1}`,
    index: i + 1,
    title: t.title,
    objective: t.objective,
    agentId: t.agentId,
    status: "WAITING",
    verification: "NONE",
    dependsOn: i === 0 ? [] : [`${id}_s${i}`],
    tools: t.tools,
    expectedState: t.expectedState,
    currentState: "Queued.",
    attempts: 0,
    maxAttempts: 3,
    requiresApproval: t.requiresApproval,
  }));

  const derived =
    goal
      .replace(/\s+/g, " ")
      .trim()
      .split(" ")
      .slice(0, 6)
      .join(" ")
      .replace(/[.,]$/, "") || "New Task";
  const derivedName = name ?? derived;

  return {
    id,
    workspaceId,
    name: derivedName.length > 48 ? `${derivedName.slice(0, 48)}…` : derivedName,
    goal: goal.trim(),
    status: "QUEUED",
    createdAt: now,
    updatedAt: now,
    executionId,
    planVersion: "v1",
    assignedAgentId: "agent_planner",
    currentStepId: steps[0].id,
    durationMs: 0,
    verification: "NONE",
    steps,
    attachments: [],
    artifactIds: [],
    approvalIds: [],
  };
}

/** A single scripted frame the player applies to the task. */
export interface SimFrame {
  status: TaskStatus;
  currentStepId?: string;
  patchStep?: { id: string; changes: Partial<TaskStep> };
  event?: ExecutionEvent;
  message: string;
  /** delay in ms before the NEXT frame */
  delay: number;
}

/** Produce the full scripted timeline for a queued task. */
export function buildScript(task: Task): SimFrame[] {
  const frames: SimFrame[] = [];
  const ev = (
    type: ExecutionEvent["type"],
    label: string,
    extra?: Partial<ExecutionEvent>,
  ): ExecutionEvent => ({
    id: nextId("ev"),
    at: new Date().toISOString(),
    type,
    label,
    ...extra,
  });

  frames.push({
    status: "PLANNING",
    message: "Planning…",
    event: ev("task.planned", "Plan generated", { agentId: "agent_planner" }),
    delay: 900,
  });
  frames.push({
    status: "VALIDATING",
    message: "Validating plan…",
    event: ev("plan.validated", "Plan validated", { agentId: "agent_planner" }),
    delay: 700,
  });

  task.steps.forEach((step) => {
    if (step.requiresApproval) {
      frames.push({
        status: "AWAITING_APPROVAL",
        currentStepId: step.id,
        patchStep: {
          id: step.id,
          changes: { status: "APPROVAL", currentState: "Awaiting approval." },
        },
        event: ev("approval.requested", "Approval required", { stepId: step.id }),
        message: "Approval required",
        delay: 0, // pause here until user approves
      });
      return;
    }

    frames.push({
      status: "RUNNING",
      currentStepId: step.id,
      patchStep: {
        id: step.id,
        changes: {
          status: "RUNNING",
          verification: "PENDING",
          currentState: stepRunningState(step),
          startedAt: new Date().toISOString(),
          attempts: 1,
        },
      },
      event: ev("agent.started", `${step.title} started`, {
        agentId: step.agentId,
        stepId: step.id,
        tool: step.tools[0],
      }),
      message: `${step.title}…`,
      delay: 1100,
    });

    frames.push({
      status: "RUNNING",
      currentStepId: step.id,
      patchStep: {
        id: step.id,
        changes: {
          status: "COMPLETE",
          verification: "PASSED",
          currentState: "Completed.",
          completedAt: new Date().toISOString(),
        },
      },
      event: ev("verification.passed", `${step.title} verified`, {
        stepId: step.id,
      }),
      message: `${step.title} ✓`,
      delay: 500,
    });
  });

  return frames;
}

function stepRunningState(step: TaskStep): string {
  const map: Record<string, string> = {
    agent_planner: "Interpreting the goal…",
    agent_research: "Retrieving authorized sources…",
    agent_spreadsheet: "Generating deliverable…",
    agent_verification: "Verifying deliverable…",
    agent_communication: "Preparing communication…",
  };
  return map[step.agentId] ?? "Working…";
}

/** Frames that resume a task after approval and drive it to completion. */
export function buildResumeScript(task: Task): SimFrame[] {
  const frames: SimFrame[] = [];
  const ev = (
    type: ExecutionEvent["type"],
    label: string,
    extra?: Partial<ExecutionEvent>,
  ): ExecutionEvent => ({
    id: nextId("ev"),
    at: new Date().toISOString(),
    type,
    label,
    ...extra,
  });

  const approvalStep = task.steps.find((s) => s.requiresApproval);
  if (approvalStep) {
    frames.push({
      status: "RUNNING",
      patchStep: {
        id: approvalStep.id,
        changes: { status: "COMPLETE", currentState: "Approved." },
      },
      event: ev("approval.granted", "Approval granted", {
        stepId: approvalStep.id,
      }),
      message: "Approved",
      delay: 700,
    });
  }

  // Any remaining post-approval steps.
  const remaining = task.steps.filter(
    (s) => !s.requiresApproval && s.status !== "COMPLETE",
  );
  remaining.forEach((step) => {
    frames.push({
      status: "RUNNING",
      currentStepId: step.id,
      patchStep: {
        id: step.id,
        changes: { status: "RUNNING", currentState: stepRunningState(step) },
      },
      event: ev("agent.started", `${step.title} started`, {
        agentId: step.agentId,
        stepId: step.id,
      }),
      message: `${step.title}…`,
      delay: 1000,
    });
    frames.push({
      status: "RUNNING",
      patchStep: {
        id: step.id,
        changes: { status: "COMPLETE", verification: "PASSED", currentState: "Completed." },
      },
      event: ev("verification.passed", `${step.title} verified`, {
        stepId: step.id,
      }),
      message: `${step.title} ✓`,
      delay: 500,
    });
  });

  frames.push({
    status: "COMPLETE",
    patchStep: undefined,
    event: ev("execution.completed", "Execution completed"),
    message: "Complete",
    delay: 0,
  });

  return frames;
}
