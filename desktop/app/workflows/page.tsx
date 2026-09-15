"use client";

import { useMemo, useState } from "react";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { backendRepository } from "@/lib/api";
import { useConnectedList } from "@/hooks/use-connected-list";
import { PageContainer, PageHeader } from "@/components/shared/page";
import { SearchField } from "@/components/shared/toolbar";
import { WorkflowCard } from "@/components/workflows/workflow-card";
import { EmptyState } from "@/components/shared/states";

export default function WorkflowsPage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const [query, setQuery] = useState("");
  const { items: workflows } = useConnectedList(
    () => backendRepository.workflows(activeWs),
    repository.workflows(activeWs),
    [activeWs],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return workflows.filter(
      (w) =>
        !q ||
        w.name.toLowerCase().includes(q) ||
        w.purpose.toLowerCase().includes(q),
    );
  }, [workflows, query]);

  return (
    <PageContainer>
      <PageHeader
        title="Workflows"
        description="Reusable, verified workflows built from successful executions."
        actions={
          <SearchField
            value={query}
            onChange={setQuery}
            placeholder="Search workflows…"
            className="w-64"
          />
        }
      />

      {filtered.length === 0 ? (
        <EmptyState
          icon="Workflow"
          title="No workflows yet"
          description="Verified workflows will appear here after successful executions."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((w) => (
            <WorkflowCard key={w.id} workflow={w} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
