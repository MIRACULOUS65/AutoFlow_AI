"use client";

import type { TaskStep } from "@/lib/types";
import { agentName } from "@/lib/mock-data/agents";
import { getTask } from "@/lib/mock-data/tasks";
import { formatTime } from "@/lib/utils";
import { MetaRow } from "@/components/shared/page";
import {
  StepStatusBadge,
  VerificationBadge,
} from "@/components/shared/status-badge";

/** Body content for the step detail drawer. */
export function StepDetail({
  step,
  allSteps,
}: {
  step: TaskStep;
  allSteps: TaskStep[];
}) {
  const deps = step.dependsOn
    .map((id) => allSteps.find((s) => s.id === id))
    .filter(Boolean) as TaskStep[];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <StepStatusBadge status={step.status} />
        <VerificationBadge state={step.verification} />
      </div>

      <div>
        <p className="text-2xs uppercase tracking-wider text-muted-foreground">
          Objective
        </p>
        <p className="mt-1 text-sm">{step.objective}</p>
      </div>

      <div className="rounded-lg border border-border px-4 py-2">
        <MetaRow label="Agent">{agentName(step.agentId)}</MetaRow>
        <MetaRow label="Attempts">
          <span className="tabular">
            {step.attempts} / {step.maxAttempts}
          </span>
        </MetaRow>
        {step.startedAt && (
          <MetaRow label="Started" mono>
            {formatTime(step.startedAt)}
          </MetaRow>
        )}
        {step.completedAt && (
          <MetaRow label="Completed" mono>
            {formatTime(step.completedAt)}
          </MetaRow>
        )}
      </div>

      <div>
        <p className="mb-1.5 text-2xs uppercase tracking-wider text-muted-foreground">
          Expected state
        </p>
        <p className="rounded-md border border-border bg-surface px-3 py-2 text-sm">
          {step.expectedState}
        </p>
      </div>

      <div>
        <p className="mb-1.5 text-2xs uppercase tracking-wider text-muted-foreground">
          Current state
        </p>
        <p className="rounded-md border border-border bg-surface px-3 py-2 text-sm">
          {step.currentState}
        </p>
      </div>

      {step.tools.length > 0 && (
        <div>
          <p className="mb-1.5 text-2xs uppercase tracking-wider text-muted-foreground">
            Tools
          </p>
          <div className="flex flex-wrap gap-1.5">
            {step.tools.map((t) => (
              <span
                key={t}
                className="rounded-md border border-border px-2 py-0.5 font-mono text-2xs"
              >
                {t}
              </span>
            ))}
          </div>
        </div>
      )}

      <div>
        <p className="mb-1.5 text-2xs uppercase tracking-wider text-muted-foreground">
          Dependencies
        </p>
        {deps.length > 0 ? (
          <ul className="space-y-1">
            {deps.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between rounded-md border border-border px-3 py-1.5 text-sm"
              >
                <span className="truncate">
                  {String(d.index).padStart(2, "0")} · {d.title}
                </span>
                <StepStatusBadge status={d.status} size="sm" showGlyph={false} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No dependencies.</p>
        )}
      </div>
    </div>
  );
}
