"use client";

import { useMemo, useState } from "react";
import { Maximize2, Minus, X } from "lucide-react";
import type { Task, TaskStep } from "@/lib/types";
import { agentName } from "@/lib/mock-data/agents";
import { getArtifact } from "@/lib/mock-data/artifacts";
import { kindIcon } from "@/lib/icons";
import { cn } from "@/lib/utils";
import { Icon } from "@/components/shared/icon";
import { TaskGraph } from "@/components/tasks/task-graph";
import { ExecutionTimeline } from "@/components/executions/execution-timeline";
import { ArtifactCard } from "@/components/artifacts/artifact-card";
import { EmptyState } from "@/components/shared/states";
import type { ExecutionEvent } from "@/lib/types";

/*
 * The center "stage".
 *
 * Before execution begins it stays deliberately clear. Once the task is
 * planning/running/etc. it becomes a live working surface: a screen-mirroring
 * viewport of whatever the active agent is producing (a document, a
 * spreadsheet, a deck), with tabs to switch to the workflow graph, timeline
 * and artifacts. This is the focal point of the whole task view.
 */

type StageTab = "mirror" | "graph" | "timeline" | "artifacts";

const IDLE_STATUSES = new Set(["QUEUED"]);

export function LiveStage({
  task,
  timeline,
  message,
  selectedStepId,
  onSelectStep,
}: {
  task: Task;
  timeline: ExecutionEvent[];
  message?: string;
  selectedStepId?: string;
  onSelectStep?: (step: TaskStep) => void;
}) {
  const [tab, setTab] = useState<StageTab>("mirror");

  const activeStep =
    task.steps.find((s) => s.status === "RUNNING") ??
    task.steps.find((s) => s.status === "RECOVERY") ??
    task.steps.find((s) => s.status === "VERIFYING") ??
    task.steps.find((s) => s.status === "APPROVAL");

  const artifacts = useMemo(
    () => task.artifactIds.map((a) => getArtifact(a)).filter(Boolean),
    [task.artifactIds],
  );

  // Real artifacts produced during this run, derived from the live event
  // stream (connected mode). Each artifact.created event carries name/path.
  const liveArtifacts = useMemo(() => {
    const out: { name: string; path?: string }[] = [];
    for (const e of task.liveEvents ?? []) {
      if (String(e.type) !== "artifact.created") continue;
      let name = e.label?.replace(/^Artifact created:\s*/i, "").trim() || "artifact";
      let path: string | undefined;
      if (e.detail) {
        try {
          const p = JSON.parse(e.detail);
          name = p.name || name;
          path = p.path || undefined;
        } catch {
          /* detail not JSON */
        }
      }
      out.push({ name, path });
    }
    return out;
  }, [task.liveEvents]);

  const notStarted = IDLE_STATUSES.has(task.status);

  // Idle: keep the stage clear.
  if (notStarted) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-sm text-center">
          <div className="mx-auto mb-5 flex size-14 items-center justify-center rounded-xl border border-border bg-surface">
            <span className="animate-pulse-ring font-mono text-xl">○</span>
          </div>
          <p className="text-sm font-medium">Stage is clear</p>
          <p className="mt-1 text-sm text-muted-foreground">
            When AutoFlow starts working, the live screen appears here — you
            will see documents and deliverables as they are produced.
          </p>
        </div>
      </div>
    );
  }

  const tabs: { key: StageTab; label: string; count?: number }[] = [
    { key: "mirror", label: "Live Screen" },
    { key: "graph", label: "Workflow" },
    { key: "timeline", label: "Timeline" },
    {
      key: "artifacts",
      label: "Artifacts",
      count: liveArtifacts.length || artifacts.length,
    },
  ];

  return (
    <div className="flex h-full flex-col">
      {/* Stage tab bar */}
      <div className="flex items-center gap-1 border-b border-border px-3 py-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              tab === t.key
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {t.label}
            {t.count !== undefined && (
              <span className="tabular opacity-70">{t.count}</span>
            )}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-1 pr-1 text-muted-foreground">
          {task.status === "RUNNING" && (
            <span className="flex items-center gap-1.5 text-2xs">
              <span className="relative flex size-1.5">
                <span className="absolute inline-flex size-1.5 animate-ping rounded-full bg-foreground/50" />
                <span className="relative inline-flex size-1.5 rounded-full bg-foreground" />
              </span>
              Live
            </span>
          )}
        </div>
      </div>

      {/* Stage body */}
      <div className="min-h-0 flex-1 overflow-hidden bg-surface/40">
        {tab === "mirror" && (
          <ScreenMirror task={task} step={activeStep} message={message} />
        )}
        {tab === "graph" && (
          <div className="h-full overflow-auto p-5">
            <TaskGraph
              steps={task.steps}
              selectedId={selectedStepId}
              onSelect={onSelectStep}
            />
          </div>
        )}
        {tab === "timeline" && (
          <div className="h-full overflow-auto p-5">
            {timeline.length > 0 ? (
              <div className="mx-auto max-w-2xl">
                <ExecutionTimeline events={timeline} />
              </div>
            ) : (
              <EmptyState
                icon="Clock"
                title="No events yet"
                description="Execution events will appear here as the task runs."
              />
            )}
          </div>
        )}
        {tab === "artifacts" && (
          <div className="h-full overflow-auto p-5">
            {liveArtifacts.length > 0 ? (
              <ul className="space-y-2">
                {liveArtifacts.map((a, i) => (
                  <li
                    key={i}
                    className="flex items-center gap-3 rounded-md border border-border bg-background px-3 py-2.5"
                  >
                    <span className="flex size-8 items-center justify-center rounded-md border border-border font-mono text-xs">
                      ✓
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{a.name}</p>
                      {a.path && (
                        <p className="truncate text-2xs text-muted-foreground">{a.path}</p>
                      )}
                    </div>
                    <span className="shrink-0 text-2xs uppercase tracking-wider text-muted-foreground">
                      verified
                    </span>
                  </li>
                ))}
              </ul>
            ) : artifacts.length > 0 ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {artifacts.map((a) => a && <ArtifactCard key={a.id} artifact={a} />)}
              </div>
            ) : (
              <EmptyState
                icon="FileBox"
                title="No artifacts yet"
                description="Deliverables produced by this task will appear here."
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * A faux "screen mirror" — a window chrome around a live preview of the
 * artifact the active agent is producing. This is a visual representation only.
 */
function ScreenMirror({
  task,
  step,
  message,
}: {
  task: Task;
  step?: TaskStep;
  message?: string;
}) {
  // Pick the artifact the current work most likely maps to (real artifact
  // metadata comes from the task; mock lookup is a best-effort label only).
  const artifact =
    task.artifactIds.map((a) => getArtifact(a)).find(Boolean) ?? undefined;

  const title =
    artifact?.name ??
    (step ? `${step.title.toLowerCase()}` : "workspace");

  const hasLive = !!task.liveEvents && task.liveEvents.length > 0;

  if (task.status === "COMPLETE" && !hasLive) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="max-w-sm text-center">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-xl border border-border bg-background font-mono text-lg">
            ✓
          </div>
          <p className="text-sm font-medium">Task complete</p>
          <p className="mt-1 text-sm text-muted-foreground">
            The deliverables are verified and available under Artifacts.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-4">
      {/* Window chrome */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background shadow-sm">
        <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2">
          <div className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full border border-border" />
            <span className="size-2.5 rounded-full border border-border" />
            <span className="size-2.5 rounded-full border border-border" />
          </div>
          <div className="mx-auto flex items-center gap-1.5 rounded-md border border-border bg-background px-2 py-0.5">
            {artifact && (
              <Icon
                name={kindIcon(artifact.kind)}
                className="size-3 text-muted-foreground"
              />
            )}
            <span className="font-mono text-2xs text-muted-foreground">
              {title}
            </span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Minus className="size-3.5" />
            <Maximize2 className="size-3" />
            <X className="size-3.5" />
          </div>
        </div>

        {/* Mirrored content — the real live activity stream. */}
        <div className="relative min-h-0 flex-1 overflow-hidden">
          <div className="af-grid pointer-events-none absolute inset-0 opacity-[0.25]" />
          <div className="relative h-full overflow-auto p-6">
            {task.liveEvents && task.liveEvents.length > 0 ? (
              <LiveActivityFeed events={task.liveEvents} status={task.status} />
            ) : (
              <div className="flex h-full items-center justify-center">
                <p className="text-sm text-muted-foreground">
                  Waiting for the first activity…
                </p>
              </div>
            )}
          </div>

          {/* Activity caption */}
          {step && task.status !== "AWAITING_APPROVAL" && (
            <div className="absolute inset-x-0 bottom-0 flex items-center gap-2 border-t border-border bg-background/90 px-4 py-2 backdrop-blur">
              <span className="relative flex size-2">
                <span className="absolute inline-flex size-2 animate-ping rounded-full bg-foreground/40" />
                <span className="relative inline-flex size-2 rounded-full bg-foreground" />
              </span>
              <span className="truncate text-xs">
                {message || step.currentState}
              </span>
              <span className="ml-auto shrink-0 text-2xs text-muted-foreground">
                {agentName(step.agentId)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Real live activity feed — renders the actual backend/SSE events (connected
 * mode) as they stream in: generating content, launching the app, typing,
 * verifying, complete. This is the honest "what AutoFlow is doing right now"
 * surface, not a skeleton mock.
 */
function LiveActivityFeed({
  events,
  status,
}: {
  events: ExecutionEvent[];
  status: Task["status"];
}) {
  const running = status === "RUNNING" || status === "PLANNING" || status === "VALIDATING";
  // Newest last; the container auto-scrolls to bottom via key on length.
  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4 flex items-center gap-2">
        <span className="text-sm font-medium">Live activity</span>
        {running && (
          <span className="flex items-center gap-1.5 text-2xs text-muted-foreground">
            <span className="relative flex size-1.5">
              <span className="absolute inline-flex size-1.5 animate-ping rounded-full bg-foreground/50" />
              <span className="relative inline-flex size-1.5 rounded-full bg-foreground" />
            </span>
            running
          </span>
        )}
      </div>
      <ol className="space-y-2">
        {events.map((e, i) => {
          const last = i === events.length - 1;
          const t = String(e.type);
          const failed = t === "execution.failed" || t === "verification.failed";
          const done = t === "execution.completed" || t === "verification.passed";
          const glyph = failed ? "×" : done ? "✓" : "•";
          return (
            <li
              key={e.id ?? i}
              className="flex items-start gap-2.5 rounded-md border border-border bg-background px-3 py-2"
            >
              <span
                className={cn(
                  "mt-0.5 flex size-4 shrink-0 items-center justify-center font-mono text-xs",
                  failed && "text-foreground",
                  last && running && "animate-pulse",
                )}
                aria-hidden
              >
                {glyph}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{e.label}</p>
                <p className="truncate text-2xs uppercase tracking-wider text-muted-foreground">
                  {e.type.replace(/\./g, " · ")}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}


