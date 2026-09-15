"use client";

import type { Task, TaskStep } from "@/lib/types";
import { agentName, getAgent } from "@/lib/mock-data/agents";
import { AGENT_ICON, STEP_STATUS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/shared/icon";
import { MetaRow, SectionHeading } from "@/components/shared/page";

/**
 * Right-hand live execution panel. Summarizes agent activity and the current
 * action without exposing any hidden reasoning — only operational state.
 */
export function LiveExecutionPanel({
  task,
  message,
}: {
  task: Task;
  message?: string;
}) {
  // Distinct agents in plan order, with their most advanced step status.
  const agentRows = deriveAgentRows(task.steps);
  const current = task.steps.find((s) => s.status === "RUNNING");
  const currentDisplay = current ?? task.steps.find((s) => s.status === "APPROVAL");

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-4">
        <SectionHeading title="Live Execution" />
        <div className="mt-3 space-y-2.5">
          {agentRows.map((row) => {
            const desc = STEP_STATUS[row.status];
            const running = row.status === "RUNNING";
            return (
              <div key={row.agentId} className="flex items-start gap-2.5">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-surface">
                  <Icon
                    name={AGENT_ICON[getAgent(row.agentId)?.kind ?? "planner"]}
                    className="size-3.5"
                  />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">
                      {agentName(row.agentId)}
                    </span>
                    <span
                      className={cn(
                        "shrink-0 font-mono text-xs",
                        running && "animate-pulse-ring",
                      )}
                      aria-hidden
                    >
                      {desc.glyph}
                    </span>
                  </div>
                  <p className="truncate text-2xs text-muted-foreground">
                    {row.detail}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="p-4">
        <SectionHeading title="Current Action" />
        {currentDisplay ? (
          <div className="mt-3 space-y-2 rounded-lg border border-border p-3">
            <p className="text-sm font-medium">
              {message || currentDisplay.currentState}
            </p>
            <div className="border-t border-border pt-2">
              <MetaRow label="Agent">
                {agentName(currentDisplay.agentId)}
              </MetaRow>
              {currentDisplay.tools[0] && (
                <MetaRow label="Tool" mono>
                  {currentDisplay.tools[0]}
                </MetaRow>
              )}
              <MetaRow label="State">
                <span className="font-mono text-xs">
                  {currentDisplay.status}
                </span>
              </MetaRow>
            </div>
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">
            {task.status === "COMPLETE"
              ? "All steps complete. No action in progress."
              : "No action currently in progress."}
          </p>
        )}
      </div>
    </div>
  );
}

function deriveAgentRows(steps: TaskStep[]) {
  const order: string[] = [];
  const byAgent = new Map<string, TaskStep[]>();
  for (const s of steps) {
    if (!byAgent.has(s.agentId)) {
      byAgent.set(s.agentId, []);
      order.push(s.agentId);
    }
    byAgent.get(s.agentId)!.push(s);
  }
  const rank: Record<TaskStep["status"], number> = {
    RUNNING: 5,
    RECOVERY: 5,
    VERIFYING: 4,
    APPROVAL: 4,
    COMPLETE: 3,
    FAILED: 3,
    READY: 2,
    WAITING: 1,
    SKIPPED: 0,
  };
  return order.map((agentId) => {
    const agentSteps = byAgent.get(agentId)!;
    const lead = [...agentSteps].sort(
      (a, b) => rank[b.status] - rank[a.status],
    )[0];
    return {
      agentId,
      status: lead.status,
      detail: lead.currentState,
    };
  });
}
