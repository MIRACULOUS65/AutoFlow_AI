"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { ExecutionStatus } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { backendRepository } from "@/lib/api";
import { useConnectedList } from "@/hooks/use-connected-list";
import { agentName } from "@/lib/mock-data/agents";
import { formatClock, formatDuration } from "@/lib/utils";
import { PageContainer, PageHeader } from "@/components/shared/page";
import { SearchField, FilterTabs } from "@/components/shared/toolbar";
import { EmptyState } from "@/components/shared/states";
import {
  TaskStatusBadge,
  VerificationBadge,
} from "@/components/shared/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Filter = "all" | "running" | "complete" | "failed";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "running", label: "Running" },
  { value: "complete", label: "Complete" },
  { value: "failed", label: "Failed" },
];

function matches(status: ExecutionStatus, f: Filter): boolean {
  if (f === "all") return true;
  if (f === "running")
    return ["RUNNING", "RECOVERY", "AWAITING_APPROVAL", "QUEUED", "VERIFYING"].includes(status);
  if (f === "complete") return status === "COMPLETE";
  return ["FAILED", "CANCELLED", "EXPIRED", "BLOCKED"].includes(status);
}

export default function ExecutionsPage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const { items: executions } = useConnectedList(
    () => backendRepository.executions(activeWs),
    repository.executions(activeWs),
    [activeWs],
  );

  const counts = useMemo(
    () => ({
      all: executions.length,
      running: executions.filter((e) => matches(e.status, "running")).length,
      complete: executions.filter((e) => matches(e.status, "complete")).length,
      failed: executions.filter((e) => matches(e.status, "failed")).length,
    }),
    [executions],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return executions
      .filter((e) => matches(e.status, filter))
      .filter(
        (e) =>
          !q ||
          e.taskName.toLowerCase().includes(q) ||
          e.id.toLowerCase().includes(q),
      )
      .sort(
        (a, b) =>
          new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
      );
  }, [executions, filter, query]);

  return (
    <PageContainer>
      <PageHeader
        title="Executions"
        description="Operational history of every run in this workspace."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchField
          value={query}
          onChange={setQuery}
          placeholder="Search executions…"
          className="w-64"
        />
        <FilterTabs
          options={FILTERS}
          value={filter}
          onChange={setFilter}
          counts={counts}
        />
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon="Activity"
          title="No executions"
          description="Runs will appear here as tasks execute."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Execution</TableHead>
                <TableHead>Task</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Agent</TableHead>
                <TableHead className="text-right">Started</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead>Verification</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((e) => (
                <TableRow key={e.id} className="cursor-pointer">
                  <TableCell>
                    <Link
                      href={`/executions/${e.id}`}
                      className="font-mono text-sm hover:underline"
                    >
                      {e.id}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-[16rem]">
                    <Link
                      href={`/executions/${e.id}`}
                      className="block truncate text-sm"
                    >
                      {e.taskName}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <TaskStatusBadge status={e.status} size="sm" />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {agentName(e.agentId)}
                  </TableCell>
                  <TableCell className="text-right text-sm tabular text-muted-foreground">
                    {formatClock(e.startedAt)}
                  </TableCell>
                  <TableCell className="text-right text-sm tabular text-muted-foreground">
                    {e.durationMs > 0 ? formatDuration(e.durationMs) : "—"}
                  </TableCell>
                  <TableCell>
                    <VerificationBadge state={e.verification} size="sm" />
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
