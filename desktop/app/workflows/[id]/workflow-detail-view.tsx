"use client";

import Link from "next/link";
import { Play } from "lucide-react";
import { repository } from "@/lib/repository";
import { agentName } from "@/lib/mock-data/agents";
import { getArtifact } from "@/lib/mock-data/artifacts";
import { formatDuration, relativeTime } from "@/lib/utils";
import { PageContainer, MetaRow, SectionHeading } from "@/components/shared/page";
import { WorkflowGraph } from "@/components/workflows/workflow-graph";
import { ArtifactCard } from "@/components/artifacts/artifact-card";
import { EmptyState } from "@/components/shared/states";
import {
  TaskStatusBadge,
  VerificationBadge,
} from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";

export function WorkflowDetailView({ id }: { id: string }) {
  const workflow = repository.workflow(id);

  if (!workflow) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon="SearchX"
          title="Workflow not found"
          action={
            <Button asChild variant="outline">
              <Link href="/workflows">Back to workflows</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const artifacts = workflow.artifactIds
    .map((aid) => getArtifact(aid))
    .filter(Boolean);

  return (
    <PageContainer>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight">
            {workflow.name}
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {workflow.purpose}
          </p>
        </div>
        <Button>
          <Play /> Run workflow
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left: graph + runs */}
        <div className="space-y-6">
          <div>
            <SectionHeading title="Steps" className="mb-3" />
            <WorkflowGraph steps={workflow.stepTitles} />
          </div>

          <div>
            <SectionHeading title="Previous Runs" className="mb-3" />
            <div className="divide-y divide-border rounded-lg border border-border">
              {workflow.history.map((r) => (
                <div key={r.id} className="flex items-center gap-3 p-3">
                  <span className="rounded border border-border px-1.5 py-0.5 font-mono text-2xs">
                    {r.version}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm">{relativeTime(r.at)}</p>
                    <p className="text-2xs tabular text-muted-foreground">
                      {formatDuration(r.durationMs)}
                    </p>
                  </div>
                  <VerificationBadge state={r.verification} size="sm" />
                  <TaskStatusBadge status={r.status} size="sm" />
                </div>
              ))}
            </div>
          </div>

          {artifacts.length > 0 && (
            <div>
              <SectionHeading title="Artifacts" className="mb-3" />
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {artifacts.map((a) => a && <ArtifactCard key={a.id} artifact={a} />)}
              </div>
            </div>
          )}
        </div>

        {/* Right: metadata + versioning */}
        <div className="space-y-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="grid grid-cols-2 gap-3 text-center">
              <div>
                <p className="text-2xl font-semibold tabular">{workflow.runs}</p>
                <p className="text-2xs text-muted-foreground">Runs</p>
              </div>
              <div>
                <p className="text-2xl font-semibold tabular">
                  {workflow.successRate}%
                </p>
                <p className="text-2xs text-muted-foreground">Verified</p>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-2xs uppercase tracking-wider text-muted-foreground">
              Version
            </p>
            <div className="flex items-center gap-2">
              <span className="rounded-md bg-foreground px-2 py-0.5 font-mono text-xs text-background">
                {workflow.version}
              </span>
              <span className="text-2xs text-muted-foreground">
                verified {relativeTime(workflow.lastVerifiedAt)}
              </span>
            </div>
            {workflow.previousVersions.length > 0 && (
              <div className="mt-3 border-t border-border pt-3">
                <p className="mb-1.5 text-2xs uppercase tracking-wider text-muted-foreground">
                  Previous
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {workflow.previousVersions.map((v) => (
                    <span
                      key={v}
                      className="rounded-md border border-border px-2 py-0.5 font-mono text-2xs text-muted-foreground"
                    >
                      {v}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-2xs uppercase tracking-wider text-muted-foreground">
              Agents
            </p>
            <ul className="space-y-1">
              {workflow.agentIds.map((aid) => (
                <li key={aid} className="text-sm">
                  {agentName(aid)}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
