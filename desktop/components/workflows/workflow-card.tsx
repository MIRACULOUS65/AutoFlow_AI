"use client";

import Link from "next/link";
import { Workflow as WorkflowIcon } from "lucide-react";
import type { Workflow } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

export function WorkflowCard({ workflow }: { workflow: Workflow }) {
  return (
    <Link
      href={`/workflows/${workflow.id}`}
      className="group flex flex-col rounded-lg border border-border bg-card p-5 transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between">
        <div className="flex size-9 items-center justify-center rounded-md border border-border bg-surface">
          <WorkflowIcon className="size-4" />
        </div>
        <span className="rounded-md border border-border px-1.5 py-0.5 font-mono text-2xs">
          {workflow.version}
        </span>
      </div>

      <h3 className="mt-3 text-sm font-medium group-hover:underline">
        {workflow.name}
      </h3>
      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
        {workflow.purpose}
      </p>

      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
        <div>
          <p className="text-sm font-semibold tabular">{workflow.runs}</p>
          <p className="text-2xs text-muted-foreground">Runs</p>
        </div>
        <div>
          <p className="text-sm font-semibold tabular">
            {workflow.successRate}%
          </p>
          <p className="text-2xs text-muted-foreground">Verified</p>
        </div>
        <div>
          <p className="truncate text-sm font-semibold">
            {relativeTime(workflow.lastVerifiedAt)}
          </p>
          <p className="text-2xs text-muted-foreground">Last run</p>
        </div>
      </div>
    </Link>
  );
}
