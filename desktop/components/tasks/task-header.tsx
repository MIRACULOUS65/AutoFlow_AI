"use client";

import { Ban, Pause, Play } from "lucide-react";
import type { Task } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { formatClock } from "@/lib/utils";
import { TaskStatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";

export function TaskHeader({ task }: { task: Task }) {
  const setTaskStatus = useAppStore((s) => s.setTaskStatus);
  const isRunning = ["RUNNING", "PLANNING", "VALIDATING", "VERIFYING"].includes(
    task.status,
  );
  const canCancel = !["COMPLETE", "FAILED", "CANCELLED"].includes(task.status);

  return (
    <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border bg-background px-6 py-4">
      <div className="min-w-0">
        <div className="flex items-center gap-3">
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {task.name}
          </h1>
          <TaskStatusBadge status={task.status} />
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-2xs text-muted-foreground">
          <span>{task.id}</span>
          {task.executionId && <span>exec {task.executionId}</span>}
          <span>plan {task.planVersion}</span>
          <span>created {formatClock(task.createdAt)}</span>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {isRunning ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTaskStatus(task.id, "BLOCKED")}
          >
            <Pause /> Pause
          </Button>
        ) : task.status === "BLOCKED" ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setTaskStatus(task.id, "RUNNING")}
          >
            <Play /> Resume
          </Button>
        ) : null}
        {canCancel && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setTaskStatus(task.id, "CANCELLED")}
          >
            <Ban /> Cancel
          </Button>
        )}
      </div>
    </div>
  );
}
