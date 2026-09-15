"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import type { Task, TaskStep } from "@/lib/types";
import { agentName, getAgent } from "@/lib/mock-data/agents";
import { AGENT_ICON, STEP_STATUS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/shared/icon";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { ApprovalPanel } from "@/components/approvals/approval-panel";
import { RecoveryPanel } from "@/components/tasks/recovery-panel";
import type { Approval } from "@/lib/types";

/*
 * Left rail — the agentic conversation surface.
 *
 * Top: the goal + a scrollable stream of agent activity, approval and recovery.
 * Bottom: a docked chat-style composer (Copilot / ChatGPT style) for follow-up
 * instructions. Interactions are local/mock in this build.
 */
export function TaskConversationRail({
  task,
  message,
  approval,
  recoveryStep,
  onApprovalResolved,
  onSelectStep,
}: {
  task: Task;
  message?: string;
  approval?: Approval;
  recoveryStep?: TaskStep;
  onApprovalResolved: (status: "APPROVED" | "REJECTED") => void;
  onSelectStep?: (step: TaskStep) => void;
}) {
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const agentRows = deriveAgentRows(task.steps);
  const current =
    task.steps.find((s) => s.status === "RUNNING") ??
    task.steps.find((s) => s.status === "APPROVAL");

  // Keep the stream pinned to the latest activity. Radix marks the real
  // scroll container with data-radix-scroll-area-viewport.
  useEffect(() => {
    const el = scrollRef.current?.querySelector<HTMLElement>(
      "[data-radix-scroll-area-viewport]",
    );
    if (el) el.scrollTop = el.scrollHeight;
  }, [message, task.status, task.steps]);

  const send = () => {
    // Follow-up instructions are local-only in this build.
    setDraft("");
  };

  return (
    <div className="flex h-full flex-col border-r border-border bg-surface">
      {/* Goal */}
      <div className="border-b border-border p-4">
        <p className="text-2xs uppercase tracking-wider text-muted-foreground">
          Goal
        </p>
        <p className="mt-1 text-sm leading-snug">{task.goal}</p>
      </div>

      {/* Activity stream */}
      <ScrollArea className="min-h-0 flex-1" ref={scrollRef}>
        <div className="space-y-4 p-4">
          {/* Agent activity */}
          <div>
            <p className="mb-2 text-2xs uppercase tracking-wider text-muted-foreground">
              Live Execution
            </p>
            <div className="space-y-2">
              {agentRows.map((row) => {
                const desc = STEP_STATUS[row.status];
                const running = row.status === "RUNNING";
                return (
                  <div key={row.agentId} className="flex items-start gap-2.5">
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-background">
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

          {/* Current action */}
          {current && (
            <div className="rounded-lg border border-border bg-background p-3">
              <p className="text-2xs uppercase tracking-wider text-muted-foreground">
                Current action
              </p>
              <p className="mt-1 text-sm font-medium">
                {message || current.currentState}
              </p>
              <div className="mt-2 flex items-center justify-between border-t border-border pt-2 text-2xs text-muted-foreground">
                <span>{agentName(current.agentId)}</span>
                {current.tools[0] && (
                  <span className="font-mono">{current.tools[0]}</span>
                )}
              </div>
            </div>
          )}

          {/* Recovery inline */}
          {recoveryStep && <RecoveryPanel task={task} step={recoveryStep} />}

          {/* Approval inline */}
          {task.status === "AWAITING_APPROVAL" && approval && (
            <div className="rounded-lg border border-foreground/40 bg-background p-4">
              <ApprovalPanel
                approval={approval}
                compact
                onResolved={onApprovalResolved}
              />
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Docked composer */}
      <div className="border-t border-border p-3">
        <div className="rounded-xl border border-border bg-background focus-within:ring-1 focus-within:ring-ring">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (draft.trim()) send();
              }
            }}
            rows={2}
            placeholder="Send a follow-up instruction…"
            className="min-h-0 resize-none border-0 bg-transparent px-3 py-2.5 text-sm shadow-none focus-visible:ring-0"
          />
          <div className="flex items-center justify-between px-2 pb-2">
            <Button
              variant="ghost"
              size="icon-sm"
              className="text-muted-foreground"
              aria-label="Attach file"
            >
              <Paperclip />
            </Button>
            <Button
              size="icon-sm"
              onClick={send}
              disabled={!draft.trim()}
              aria-label="Send"
            >
              <ArrowUp />
            </Button>
          </div>
        </div>
        <p className="mt-1.5 px-1 text-2xs text-muted-foreground">
          AutoFlow asks before any external action.
        </p>
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
    return { agentId, status: lead.status, detail: lead.currentState };
  });
}
