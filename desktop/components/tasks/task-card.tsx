"use client";

import Link from "next/link";
import { Clock } from "lucide-react";
import type { Task } from "@/lib/types";
import { agentName } from "@/lib/mock-data/agents";
import { formatDuration, relativeTime, truncateId } from "@/lib/utils";
import { TaskStatusBadge, VerificationBadge } from "@/components/shared/status-badge";

export function TaskCard({ task }: { task: Task }) {
  const completed = task.steps.filter((s) => s.status === "COMPLETE").length;
  return (
    <Link
      href={`/tasks/${task.id}`}
      className="group flex flex-col rounded-lg border border-border bg-card p-4 transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium group-hover:underline">
            {task.name}
          </h3>
          <p className="mt-0.5 font-mono text-2xs text-muted-foreground">
            {truncateId(task.id, 14)}
          </p>
        </div>
        <TaskStatusBadge status={task.status} size="sm" />
      </div>

      <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
        {task.goal}
      </p>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3 text-2xs text-muted-foreground">
        <span className="flex items-center gap-3">
          <span>{agentName(task.assignedAgentId)}</span>
          <span className="tabular">
            {completed}/{task.steps.length} steps
          </span>
        </span>
        <span className="flex items-center gap-2">
          {task.verification !== "NONE" && (
            <VerificationBadge state={task.verification} size="sm" showGlyph />
          )}
          <span className="flex items-center gap-1 tabular">
            <Clock className="size-3" />
            {task.durationMs > 0
              ? formatDuration(task.durationMs)
              : relativeTime(task.createdAt)}
          </span>
        </span>
      </div>
    </Link>
  );
}
