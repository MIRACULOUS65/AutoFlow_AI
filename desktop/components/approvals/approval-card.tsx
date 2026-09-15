"use client";

import { ChevronRight } from "lucide-react";
import type { Approval } from "@/lib/types";
import { relativeTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { ApprovalStatusBadge } from "@/components/shared/status-badge";

export function ApprovalCard({
  approval,
  index,
  selected,
  onSelect,
}: {
  approval: Approval;
  index?: number;
  selected?: boolean;
  onSelect?: (a: Approval) => void;
}) {
  return (
    <button
      onClick={() => onSelect?.(approval)}
      className={cn(
        "group flex w-full items-center gap-3 rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        selected
          ? "border-foreground bg-surface"
          : "border-border bg-card hover:border-foreground/30",
      )}
    >
      {index !== undefined && (
        <span className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border font-mono text-xs tabular">
          {String(index).padStart(2, "0")}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{approval.action}</p>
        <p className="mt-0.5 truncate text-2xs text-muted-foreground">
          {approval.category} · requested {relativeTime(approval.requestedAt)}
        </p>
      </div>
      <ApprovalStatusBadge status={approval.status} size="sm" />
      <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
    </button>
  );
}
