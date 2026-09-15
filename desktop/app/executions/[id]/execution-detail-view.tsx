"use client";

import Link from "next/link";
import { repository } from "@/lib/repository";
import { agentName } from "@/lib/mock-data/agents";
import { getArtifact } from "@/lib/mock-data/artifacts";
import { formatClock, formatDuration } from "@/lib/utils";
import { PageContainer, MetaRow, SectionHeading } from "@/components/shared/page";
import { ExecutionTimeline } from "@/components/executions/execution-timeline";
import { ArtifactCard } from "@/components/artifacts/artifact-card";
import { EmptyState } from "@/components/shared/states";
import {
  TaskStatusBadge,
  VerificationBadge,
} from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";

export function ExecutionDetailView({ id }: { id: string }) {
  const execution = repository.execution(id);

  if (!execution) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon="SearchX"
          title="Execution not found"
          action={
            <Button asChild variant="outline">
              <Link href="/executions">Back to executions</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const task = repository.task(execution.taskId);
  const artifacts = execution.artifactIds
    .map((aid) => getArtifact(aid))
    .filter(Boolean);

  return (
    <PageContainer>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-lg font-semibold">{execution.id}</h1>
            <TaskStatusBadge status={execution.status} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {execution.taskName}
          </p>
        </div>
        {task && (
          <Button asChild variant="outline">
            <Link href={`/tasks/${task.id}`}>Open task</Link>
          </Button>
        )}
      </div>

      {/* Overview metrics */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Duration
          </p>
          <p className="mt-2 text-xl font-semibold tabular">
            {execution.durationMs > 0
              ? formatDuration(execution.durationMs)
              : "—"}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Events
          </p>
          <p className="mt-2 text-xl font-semibold tabular">
            {execution.events.length}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Artifacts
          </p>
          <p className="mt-2 text-xl font-semibold tabular">
            {artifacts.length}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Verification
          </p>
          <div className="mt-2">
            <VerificationBadge state={execution.verification} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Timeline + artifacts */}
        <div className="space-y-6">
          <div>
            <SectionHeading title="Timeline" className="mb-3" />
            <div className="rounded-lg border border-border bg-card p-4">
              <ExecutionTimeline events={execution.events} />
            </div>
          </div>

          {artifacts.length > 0 && (
            <div>
              <SectionHeading title="Artifacts" className="mb-3" />
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {artifacts.map(
                  (a) => a && <ArtifactCard key={a.id} artifact={a} />,
                )}
              </div>
            </div>
          )}
        </div>

        {/* Overview */}
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <SectionHeading title="Overview" className="mb-2" />
            <MetaRow label="Execution" mono>
              {execution.id}
            </MetaRow>
            {task && (
              <MetaRow label="Task" mono>
                {task.id}
              </MetaRow>
            )}
            <MetaRow label="Plan">{execution.planVersion}</MetaRow>
            <MetaRow label="Lead agent">{agentName(execution.agentId)}</MetaRow>
            <MetaRow label="Started" mono>
              {formatClock(execution.startedAt)}
            </MetaRow>
            {execution.endedAt && (
              <MetaRow label="Ended" mono>
                {formatClock(execution.endedAt)}
              </MetaRow>
            )}
          </div>

          {task && (
            <div className="rounded-lg border border-border bg-card p-4">
              <SectionHeading title="Agents" className="mb-2" />
              <ul className="space-y-1">
                {Array.from(new Set(task.steps.map((s) => s.agentId))).map(
                  (aid) => (
                    <li key={aid} className="text-sm">
                      {agentName(aid)}
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
