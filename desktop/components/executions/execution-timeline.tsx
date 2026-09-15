"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { ExecutionEvent } from "@/lib/types";
import { agentName } from "@/lib/mock-data/agents";
import { formatTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

const EVENT_GLYPH: Record<string, string> = {
  "task.created": "○",
  "task.planned": "◐",
  "plan.validated": "◌",
  "agent.started": "●",
  "tool.requested": "→",
  "tool.completed": "✓",
  "observation.created": "◉",
  "verification.passed": "✓",
  "verification.failed": "×",
  "approval.requested": "!",
  "approval.granted": "✓",
  "approval.rejected": "×",
  "recovery.started": "↻",
  "recovery.completed": "✓",
  "execution.completed": "✓",
  "execution.failed": "×",
};

export function ExecutionTimeline({
  events,
  className,
}: {
  events: ExecutionEvent[];
  className?: string;
}) {
  return (
    <ol className={cn("relative", className)}>
      {events.map((e, i) => (
        <TimelineRow key={e.id} event={e} last={i === events.length - 1} />
      ))}
    </ol>
  );
}

function TimelineRow({
  event,
  last,
}: {
  event: ExecutionEvent;
  last: boolean;
}) {
  const [open, setOpen] = useState(false);
  const hasDetail =
    event.agentId || event.stepId || event.tool || event.detail;

  return (
    <li className="relative flex gap-3 pl-1">
      {/* Rail */}
      <div className="flex flex-col items-center">
        <span
          className="flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-background font-mono text-2xs"
          aria-hidden
        >
          {EVENT_GLYPH[event.type] ?? "·"}
        </span>
        {!last && <span className="w-px flex-1 bg-border" />}
      </div>

      <div className="min-w-0 flex-1 pb-4">
        <button
          onClick={() => hasDetail && setOpen((v) => !v)}
          className={cn(
            "flex w-full items-center gap-2 text-left",
            hasDetail && "cursor-pointer",
          )}
        >
          <span className="font-mono text-2xs tabular text-muted-foreground">
            {formatTime(event.at)}
          </span>
          <span className="truncate text-sm">{event.label}</span>
          {hasDetail && (
            <ChevronRight
              className={cn(
                "ml-auto size-3.5 shrink-0 text-muted-foreground transition-transform",
                open && "rotate-90",
              )}
            />
          )}
        </button>

        {open && hasDetail && (
          <div className="mt-2 space-y-1 rounded-md border border-border bg-surface p-2.5 text-2xs">
            {event.agentId && (
              <Detail label="Agent" value={agentName(event.agentId)} />
            )}
            {event.stepId && (
              <Detail label="Step" value={event.stepId} mono />
            )}
            <Detail label="Event" value={event.type} mono />
            {event.tool && <Detail label="Tool" value={event.tool} mono />}
            {event.detail && <Detail label="Detail" value={event.detail} />}
          </div>
        )}
      </div>
    </li>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className={mono ? "font-mono" : ""}>{value}</span>
    </div>
  );
}
