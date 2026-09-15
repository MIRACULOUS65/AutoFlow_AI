"use client";

import { useMemo, useState } from "react";
import type { KnowledgeType } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { backendRepository } from "@/lib/api";
import { useConnectedList } from "@/hooks/use-connected-list";
import { PageContainer, PageHeader } from "@/components/shared/page";
import { SearchField, FilterTabs } from "@/components/shared/toolbar";
import { KnowledgeRow } from "@/components/knowledge/knowledge-row";
import { EmptyState } from "@/components/shared/states";

type Filter = "all" | KnowledgeType;

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "policy", label: "Policies" },
  { value: "sop", label: "SOPs" },
  { value: "procedure", label: "Procedures" },
  { value: "handbook", label: "Handbooks" },
  { value: "guide", label: "Guides" },
];

export default function KnowledgePage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const { items: sources } = useConnectedList(
    () => backendRepository.knowledge(activeWs),
    repository.knowledge(activeWs),
    [activeWs],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sources
      .filter((s) => filter === "all" || s.type === filter)
      .filter(
        (s) =>
          !q ||
          s.title.toLowerCase().includes(q) ||
          s.summary.toLowerCase().includes(q) ||
          s.provenance.toLowerCase().includes(q),
      );
  }, [sources, query, filter]);

  return (
    <PageContainer>
      <PageHeader
        title="Knowledge"
        description="Approved organizational sources agents can retrieve from, with provenance."
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchField
          value={query}
          onChange={setQuery}
          placeholder="Search knowledge…"
          className="w-64"
        />
        <FilterTabs options={FILTERS} value={filter} onChange={setFilter} />
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon="BookMarked"
          title="No knowledge sources"
          description="Approved sources for this workspace will appear here."
        />
      ) : (
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border">
          {filtered.map((s) => (
            <KnowledgeRow key={s.id} source={s} />
          ))}
        </div>
      )}
    </PageContainer>
  );
}
