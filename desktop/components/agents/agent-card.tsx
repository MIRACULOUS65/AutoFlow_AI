"use client";

import Link from "next/link";
import type { Agent } from "@/lib/types";
import { AGENT_ICON } from "@/lib/constants";
import { Icon } from "@/components/shared/icon";
import { AgentStatusBadge } from "@/components/shared/status-badge";

export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="group flex flex-col rounded-lg border border-border bg-card p-5 transition-colors hover:border-foreground/30 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    >
      <div className="flex items-start justify-between">
        <div className="flex size-9 items-center justify-center rounded-md border border-border bg-surface">
          <Icon name={AGENT_ICON[agent.kind]} className="size-4.5 size-4" />
        </div>
        <AgentStatusBadge status={agent.status} size="sm" />
      </div>

      <h3 className="mt-3 text-sm font-medium group-hover:underline">
        {agent.name}
      </h3>
      <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
        {agent.summary}
      </p>

      <div className="mt-4 space-y-2 border-t border-border pt-3">
        <div>
          <p className="text-2xs uppercase tracking-wider text-muted-foreground">
            Capabilities
          </p>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {agent.capabilities.slice(0, 3).map((c) => (
              <span
                key={c}
                className="rounded border border-border px-1.5 py-0.5 text-2xs text-muted-foreground"
              >
                {c}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center justify-between pt-1 text-2xs text-muted-foreground">
          <span>{agent.tools.length} tools</span>
          <span className="tabular">
            {agent.stats.verificationRate}% verified
          </span>
        </div>
      </div>
    </Link>
  );
}
