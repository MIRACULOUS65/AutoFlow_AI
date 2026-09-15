"use client";

import Link from "next/link";
import { repository } from "@/lib/repository";
import { AGENT_ICON } from "@/lib/constants";
import { formatDuration, relativeTime } from "@/lib/utils";
import { Icon } from "@/components/shared/icon";
import { PageContainer, MetaRow } from "@/components/shared/page";
import { EmptyState } from "@/components/shared/states";
import {
  AgentStatusBadge,
  TaskStatusBadge,
} from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function AgentDetailView({ id }: { id: string }) {
  const agent = repository.agent(id);

  if (!agent) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon="SearchX"
          title="Agent not found"
          action={
            <Button asChild variant="outline">
              <Link href="/agents">Back to agents</Link>
            </Button>
          }
        />
      </div>
    );
  }

  // Runs that used this agent.
  const runs = repository
    .executions()
    .filter((e) => e.agentId === agent.id)
    .slice(0, 6);

  const stats = [
    { label: "Tasks completed", value: agent.stats.tasksCompleted },
    { label: "Verification rate", value: `${agent.stats.verificationRate}%` },
    { label: "Avg duration", value: formatDuration(agent.stats.avgDurationMs) },
    { label: "Active runs", value: agent.stats.activeRuns },
  ];

  return (
    <PageContainer>
      {/* Header */}
      <div className="mb-6 flex flex-wrap items-start gap-4">
        <div className="flex size-12 items-center justify-center rounded-lg border border-border bg-surface">
          <Icon name={AGENT_ICON[agent.kind]} className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight">
              {agent.name}
            </h1>
            <AgentStatusBadge status={agent.status} />
          </div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {agent.summary}
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-lg border border-border bg-card p-4">
            <p className="text-xs uppercase tracking-wider text-muted-foreground">
              {s.label}
            </p>
            <p className="mt-2 text-2xl font-semibold tabular">{s.value}</p>
          </div>
        ))}
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="tools">Tools ({agent.tools.length})</TabsTrigger>
          <TabsTrigger value="runs">Recent Runs</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-medium">Responsibility</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                {agent.description}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-card p-5">
              <h2 className="text-sm font-medium">Capabilities</h2>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {agent.capabilities.map((c) => (
                  <span
                    key={c}
                    className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground"
                  >
                    {c}
                  </span>
                ))}
              </div>
              <div className="mt-4 border-t border-border pt-3">
                <MetaRow label="Kind">{agent.kind}</MetaRow>
                <MetaRow label="Last activity">{agent.recentActivity}</MetaRow>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="tools">
          <div className="divide-y divide-border rounded-lg border border-border">
            {agent.tools.map((t) => (
              <div key={t.id} className="flex items-start gap-3 p-4">
                <span className="mt-0.5 flex size-7 items-center justify-center rounded-md border border-border bg-surface font-mono text-2xs">
                  fn
                </span>
                <div>
                  <p className="font-mono text-sm">{t.name}</p>
                  <p className="text-2xs text-muted-foreground">
                    {t.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="runs">
          {runs.length > 0 ? (
            <div className="divide-y divide-border rounded-lg border border-border">
              {runs.map((r) => (
                <Link
                  key={r.id}
                  href={`/executions/${r.id}`}
                  className="flex items-center gap-3 p-3 transition-colors hover:bg-accent/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{r.taskName}</p>
                    <p className="font-mono text-2xs text-muted-foreground">
                      {r.id} · {relativeTime(r.startedAt)}
                    </p>
                  </div>
                  <TaskStatusBadge status={r.status} size="sm" />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState
              icon="Activity"
              title="No recent runs"
              description="Executions that used this agent will appear here."
            />
          )}
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
