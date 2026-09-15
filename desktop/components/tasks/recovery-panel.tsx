"use client";

import { useState } from "react";
import type { Task, TaskStep } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/*
 * Recovery surface. States facts calmly — never dramatizes, never implies
 * success while incomplete. Progresses through re-observe → re-resolve →
 * retry, ending in recovered or a safe failure with no external action taken.
 */

const PHASES = [
  { key: "RE_OBSERVING", label: "Re-observing", detail: "Re-checking the target state." },
  { key: "RE_RESOLVING", label: "Re-resolving", detail: "Resolving the target again." },
  { key: "RETRYING", label: "Retrying", detail: "Retrying the step safely." },
] as const;

export function RecoveryPanel({
  task,
  step,
}: {
  task: Task;
  step: TaskStep;
}) {
  const [phase, setPhase] = useState(0);
  const [outcome, setOutcome] = useState<"pending" | "recovered" | "failed">(
    "pending",
  );

  const advance = () => {
    if (phase < PHASES.length - 1) {
      setPhase((p) => p + 1);
    } else {
      setOutcome("recovered");
    }
  };

  if (outcome === "recovered") {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="flex items-center gap-2 text-sm font-medium">
          <span className="font-mono">✓</span> Step {step.index} recovered
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          The target was verified and the step completed safely.
        </p>
      </div>
    );
  }

  if (outcome === "failed") {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="text-sm font-medium">Could not safely complete this step.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          No external action was performed.
        </p>
        <p className="mt-3 text-2xs uppercase tracking-wider text-muted-foreground">
          Reason
        </p>
        <p className="text-sm">The target could not be verified.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => { setOutcome("pending"); setPhase(0); }}>
            Retry
          </Button>
          <Button size="sm" variant="outline">
            Resume Manually
          </Button>
          <Button size="sm" variant="ghost">
            End Task
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">
            Step {step.index} needs recovery
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            The application state changed. AutoFlow is re-checking the target.
          </p>
        </div>
        <span className="shrink-0 rounded-md border border-border px-2 py-0.5 font-mono text-2xs tabular">
          Attempt {step.attempts} / {step.maxAttempts}
        </span>
      </div>

      {/* Phase progression */}
      <div className="mt-4 flex items-center gap-1.5">
        {PHASES.map((p, i) => (
          <div key={p.key} className="flex flex-1 flex-col gap-1">
            <span
              className={cn(
                "h-1 rounded-full transition-colors",
                i <= phase ? "bg-foreground" : "bg-border",
              )}
            />
            <span
              className={cn(
                "text-2xs",
                i === phase ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {p.label}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-sm text-muted-foreground">
        {PHASES[phase].detail}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" onClick={advance}>
          {phase < PHASES.length - 1 ? "Continue recovery" : "Complete recovery"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => setOutcome("failed")}
        >
          View Details
        </Button>
        <Button size="sm" variant="ghost">
          Pause
        </Button>
        <Button size="sm" variant="ghost">
          Cancel
        </Button>
      </div>
    </div>
  );
}
