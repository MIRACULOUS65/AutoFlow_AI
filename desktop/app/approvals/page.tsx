"use client";

import { useEffect, useMemo, useState } from "react";
import { useAppStore } from "@/lib/store";
import { backendRepository, isBackendEnabled } from "@/lib/api";
import { PageContainer, PageHeader } from "@/components/shared/page";
import { FilterTabs } from "@/components/shared/toolbar";
import { ApprovalCard } from "@/components/approvals/approval-card";
import { ApprovalPanel } from "@/components/approvals/approval-panel";
import { EmptyState } from "@/components/shared/states";

type Filter = "pending" | "history";

export default function ApprovalsPage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const storeApprovals = useAppStore((s) => s.approvals);
  const setApprovals = useAppStore((s) => s.setApprovals);
  const [filter, setFilter] = useState<Filter>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Connected mode: load real approvals from the Control Plane (replacing mock
  // seed data so only real decisions are shown).
  useEffect(() => {
    if (!isBackendEnabled()) return;
    let cancelled = false;
    backendRepository
      .approvals(activeWs)
      .then((rows) => {
        if (!cancelled) setApprovals(rows);
      })
      .catch(() => {
        if (!cancelled) setApprovals([]);
      });
    return () => {
      cancelled = true;
    };
  }, [activeWs, setApprovals]);

  const scoped = useMemo(
    () =>
      isBackendEnabled()
        ? storeApprovals
        : storeApprovals.filter((a) => a.workspaceId === activeWs),
    [storeApprovals, activeWs],
  );

  const pending = scoped.filter((a) => a.status === "PENDING");
  const history = scoped.filter((a) => a.status !== "PENDING");
  const list = filter === "pending" ? pending : history;

  // Keep a valid selection.
  useEffect(() => {
    if (list.length === 0) {
      setSelectedId(null);
    } else if (!list.some((a) => a.id === selectedId)) {
      setSelectedId(list[0].id);
    }
  }, [list, selectedId]);

  const selected = scoped.find((a) => a.id === selectedId);

  return (
    <PageContainer scroll={false}>
      <div className="flex h-full flex-col">
        <div className="border-b border-border px-6 py-5">
          <PageHeader
            title="Approvals"
            description="Decisions AutoFlow needs before any external or high-impact action."
            className="pb-0"
          />
          <div className="mt-4">
            <FilterTabs
              options={[
                { value: "pending", label: "Pending" },
                { value: "history", label: "History" },
              ]}
              value={filter}
              onChange={setFilter}
              counts={{ pending: pending.length, history: history.length }}
            />
          </div>
        </div>

        <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[380px_1fr]">
          {/* List */}
          <div className="min-h-0 overflow-y-auto border-r border-border p-4">
            {list.length > 0 ? (
              <div className="space-y-2">
                {list.map((a, i) => (
                  <ApprovalCard
                    key={a.id}
                    approval={a}
                    index={filter === "pending" ? i + 1 : undefined}
                    selected={a.id === selectedId}
                    onSelect={() => setSelectedId(a.id)}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                icon="BadgeCheck"
                title={
                  filter === "pending"
                    ? "No pending approvals"
                    : "No approval history"
                }
                description={
                  filter === "pending"
                    ? "Everything requiring your decision will appear here."
                    : "Resolved approvals will be listed here."
                }
              />
            )}
          </div>

          {/* Detail */}
          <div className="min-h-0 overflow-y-auto p-6">
            {selected ? (
              <div className="mx-auto max-w-xl">
                <ApprovalPanel
                  approval={selected}
                  onResolved={() => setFilter("pending")}
                />
              </div>
            ) : (
              <div className="flex h-full items-center justify-center">
                <EmptyState
                  icon="MousePointerClick"
                  title="Select an approval"
                  description="Choose an item to review its evidence and decide."
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </PageContainer>
  );
}
