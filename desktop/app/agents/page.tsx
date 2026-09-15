"use client";

import { useMemo, useState } from "react";
import { repository } from "@/lib/repository";
import { PageContainer, PageHeader } from "@/components/shared/page";
import { SearchField } from "@/components/shared/toolbar";
import { AgentCard } from "@/components/agents/agent-card";
import { EmptyState } from "@/components/shared/states";

export default function AgentsPage() {
  const [query, setQuery] = useState("");
  const agents = repository.agents();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return agents.filter(
      (a) =>
        !q ||
        a.name.toLowerCase().includes(q) ||
        a.summary.toLowerCase().includes(q) ||
        a.capabilities.some((c) => c.toLowerCase().includes(q)),
    );
  }, [agents, query]);

  return (
    <PageContainer>
      <PageHeader
        title="Agents"
        description="Specialist capabilities AutoFlow assigns to steps in a workflow."
        actions={
          <SearchField
            value={query}
            onChange={setQuery}
            placeholder="Search agents…"
            className="w-64"
          />
        }
      />

      {filtered.length === 0 ? (
        <EmptyState
          icon="Bot"
          title="No agents found"
          description="Try a different search."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((a) => (
            <AgentCard key={a.id} agent={a} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
