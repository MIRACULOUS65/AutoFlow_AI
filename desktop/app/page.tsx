"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { agentName } from "@/lib/mock-data/agents";
import { APP_TAGLINE } from "@/lib/constants";
import { formatClock, formatDuration } from "@/lib/utils";
import { PageContainer, SectionHeading } from "@/components/shared/page";
import { TaskComposer } from "@/components/tasks/task-composer";
import { TaskCard } from "@/components/tasks/task-card";
import { EmptyState } from "@/components/shared/states";
import {
  TaskStatusBadge,
  VerificationBadge,
} from "@/components/shared/status-badge";

export default function HomePage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const tasks = useAppStore((s) => s.tasks).filter(
    (t) => t.workspaceId === activeWs,
  );
  const approvals = useAppStore((s) => s.approvals).filter(
    (a) => a.workspaceId === activeWs,
  );

  const activeTasks = tasks.filter((t) =>
    ["QUEUED", "PLANNING", "VALIDATING", "RUNNING", "VERIFYING", "RECOVERY", "AWAITING_APPROVAL"].includes(
      t.status,
    ),
  );
  const executions = repository.executions(activeWs);
  const pending = approvals.filter((a) => a.status === "PENDING");

  const counts = {
    running: tasks.filter((t) => ["RUNNING", "VERIFYING", "RECOVERY"].includes(t.status)).length,
    approval: pending.length,
    complete: tasks.filter((t) => t.status === "COMPLETE").length,
    failed: tasks.filter((t) => t.status === "FAILED").length,
  };

  return (
    <PageContainer>
      {/* Hero composer */}
      <div className="mb-8">
        <p className="mb-3 text-sm text-muted-foreground">{APP_TAGLINE}</p>
        <TaskComposer />
      </div>

      {/* Overview metrics */}
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Running", value: counts.running, glyph: "●" },
          { label: "Approval", value: counts.approval, glyph: "!" },
          { label: "Completed", value: counts.complete, glyph: "✓" },
          { label: "Failed", value: counts.failed, glyph: "×" },
        ].map((m) => (
          <div key={m.label} className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider text-muted-foreground">
                {m.label}
              </span>
              <span className="font-mono text-sm text-muted-foreground">
                {m.glyph}
              </span>
            </div>
            <p className="mt-2 text-2xl font-semibold tabular">{m.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Active tasks */}
        <div className="lg:col-span-2">
          <SectionHeading
            title="Active Tasks"
            action={
              <Link
                href="/tasks"
                className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
              >
                All tasks <ArrowRight className="size-3" />
              </Link>
            }
          />
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {activeTasks.length > 0 ? (
              activeTasks
                .slice(0, 4)
                .map((t) => <TaskCard key={t.id} task={t} />)
            ) : (
              <div className="sm:col-span-2">
                <EmptyState
                  icon="ListChecks"
                  title="No active tasks"
                  description="Start with a goal and AutoFlow will build the workflow."
                />
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <div className="space-y-8">
          {/* Approval queue */}
          <div>
            <SectionHeading
              title="Approval Queue"
              action={
                <Link
                  href="/approvals"
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  View <ArrowRight className="size-3" />
                </Link>
              }
            />
            <div className="mt-3 space-y-2">
              {pending.length > 0 ? (
                pending.slice(0, 3).map((a) => (
                  <Link
                    key={a.id}
                    href="/approvals"
                    className="flex items-center gap-3 rounded-md border border-border bg-card p-3 transition-colors hover:border-foreground/30"
                  >
                    <span className="font-mono text-sm" aria-hidden>
                      !
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.action}</p>
                      <p className="truncate text-2xs text-muted-foreground">
                        {a.category}
                      </p>
                    </div>
                  </Link>
                ))
              ) : (
                <EmptyState
                  icon="BadgeCheck"
                  title="No pending approvals"
                  description="Everything requiring your decision will appear here."
                  className="py-10"
                />
              )}
            </div>
          </div>

          {/* Recent executions */}
          <div>
            <SectionHeading
              title="Recent Executions"
              action={
                <Link
                  href="/executions"
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  View <ArrowRight className="size-3" />
                </Link>
              }
            />
            <div className="mt-3 divide-y divide-border rounded-lg border border-border">
              {executions.slice(0, 5).map((e) => (
                <Link
                  key={e.id}
                  href={`/executions/${e.id}`}
                  className="flex items-center gap-3 p-3 transition-colors hover:bg-accent/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{e.taskName}</p>
                    <p className="font-mono text-2xs text-muted-foreground">
                      {e.id} · {agentName(e.agentId)}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <TaskStatusBadge status={e.status} size="sm" />
                    <span className="text-2xs tabular text-muted-foreground">
                      {e.durationMs > 0
                        ? formatDuration(e.durationMs)
                        : formatClock(e.startedAt)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
