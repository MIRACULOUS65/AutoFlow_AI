"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { LayoutGrid, List, Plus } from "lucide-react";
import type { Task, TaskStatus } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { agentName } from "@/lib/mock-data/agents";
import { cn, formatDuration, relativeTime, truncateId } from "@/lib/utils";
import { PageContainer, PageHeader } from "@/components/shared/page";
import { SearchField, FilterTabs } from "@/components/shared/toolbar";
import { TaskCard } from "@/components/tasks/task-card";
import { EmptyState } from "@/components/shared/states";
import {
  TaskStatusBadge,
  VerificationBadge,
} from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Filter = "all" | "active" | "approval" | "complete" | "failed";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "active", label: "Active" },
  { value: "approval", label: "Approval" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" },
];

const ACTIVE_STATUSES: TaskStatus[] = [
  "QUEUED",
  "PLANNING",
  "VALIDATING",
  "RUNNING",
  "VERIFYING",
  "RECOVERY",
];

function matchesFilter(task: Task, filter: Filter): boolean {
  switch (filter) {
    case "active":
      return ACTIVE_STATUSES.includes(task.status);
    case "approval":
      return task.status === "AWAITING_APPROVAL";
    case "complete":
      return task.status === "COMPLETE";
    case "failed":
      return ["FAILED", "CANCELLED", "BLOCKED", "EXPIRED"].includes(task.status);
    default:
      return true;
  }
}

export default function TasksPage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const allTasks = useAppStore((s) => s.tasks);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [view, setView] = useState<"list" | "grid">("list");

  const tasks = useMemo(
    () => allTasks.filter((t) => t.workspaceId === activeWs),
    [allTasks, activeWs],
  );

  const counts = useMemo(
    () => ({
      all: tasks.length,
      active: tasks.filter((t) => matchesFilter(t, "active")).length,
      approval: tasks.filter((t) => matchesFilter(t, "approval")).length,
      complete: tasks.filter((t) => matchesFilter(t, "complete")).length,
      failed: tasks.filter((t) => matchesFilter(t, "failed")).length,
    }),
    [tasks],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tasks
      .filter((t) => matchesFilter(t, filter))
      .filter(
        (t) =>
          !q ||
          t.name.toLowerCase().includes(q) ||
          t.goal.toLowerCase().includes(q) ||
          t.id.toLowerCase().includes(q),
      )
      .sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      );
  }, [tasks, filter, query]);

  return (
    <PageContainer>
      <PageHeader
        title="Tasks"
        description="Every goal AutoFlow is executing or has executed in this workspace."
        actions={
          <Button asChild>
            <Link href="/">
              <Plus /> New Task
            </Link>
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <SearchField
            value={query}
            onChange={setQuery}
            placeholder="Search tasks…"
            className="w-64"
          />
          <FilterTabs
            options={FILTERS}
            value={filter}
            onChange={setFilter}
            counts={counts}
          />
        </div>
        <div className="inline-flex items-center gap-0.5 rounded-md border border-border bg-surface p-0.5">
          <button
            onClick={() => setView("list")}
            className={cn(
              "flex size-7 items-center justify-center rounded-[5px]",
              view === "list"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
            aria-label="List view"
          >
            <List className="size-4" />
          </button>
          <button
            onClick={() => setView("grid")}
            className={cn(
              "flex size-7 items-center justify-center rounded-[5px]",
              view === "grid"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
            aria-label="Grid view"
          >
            <LayoutGrid className="size-4" />
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon="ListChecks"
          title="No tasks found"
          description={
            query || filter !== "all"
              ? "Try a different search or filter."
              : "Start with a goal and AutoFlow will build the workflow."
          }
          action={
            <Button asChild>
              <Link href="/">
                <Plus /> New Task
              </Link>
            </Button>
          }
        />
      ) : view === "grid" ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((t) => (
            <TaskCard key={t.id} task={t} />
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Task</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead>Verification</TableHead>
                <TableHead className="text-right">Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((t) => (
                <TableRow key={t.id} className="cursor-pointer">
                  <TableCell className="max-w-xs">
                    <Link href={`/tasks/${t.id}`} className="block">
                      <span className="block truncate font-medium hover:underline">
                        {t.name}
                      </span>
                      <span className="block truncate font-mono text-2xs text-muted-foreground">
                        {truncateId(t.id, 16)}
                      </span>
                    </Link>
                  </TableCell>
                  <TableCell>
                    <TaskStatusBadge status={t.status} size="sm" />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {agentName(t.assignedAgentId)}
                  </TableCell>
                  <TableCell className="text-right text-sm tabular text-muted-foreground">
                    {t.durationMs > 0 ? formatDuration(t.durationMs) : "—"}
                  </TableCell>
                  <TableCell>
                    <VerificationBadge state={t.verification} size="sm" />
                  </TableCell>
                  <TableCell className="text-right text-sm tabular text-muted-foreground">
                    {relativeTime(t.createdAt)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </PageContainer>
  );
}
