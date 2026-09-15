"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, X } from "lucide-react";
import type { Approval } from "@/lib/types";
import { relativeTime } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { backendRepository, isBackendEnabled } from "@/lib/api";
import { MetaRow } from "@/components/shared/page";
import { ApprovalStatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

/**
 * Detailed approval review surface, shown in the approvals page, in a modal,
 * or inside the task detail.
 *
 * Connected mode: Approve/Reject call the real Control Plane
 * (POST /approvals/{id}/approve|reject) — the backend recomputes the action
 * hash, validates the plan version, and only then resumes the real mission.
 * Mock mode (default, no backend configured): decisions mutate local state.
 */
export function ApprovalPanel({
  approval,
  onResolved,
  compact,
}: {
  approval: Approval;
  onResolved?: (status: "APPROVED" | "REJECTED") => void;
  compact?: boolean;
}) {
  const resolveApproval = useAppStore((s) => s.resolveApproval);
  const setTaskStatus = useAppStore((s) => s.setTaskStatus);
  const pending = approval.status === "PENDING";
  const [submitting, setSubmitting] = useState<"APPROVED" | "REJECTED" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const decide = async (status: "APPROVED" | "REJECTED") => {
    if (submitting) return;
    setSubmitting(status);
    setError(null);
    try {
      if (isBackendEnabled()) {
        if (status === "APPROVED") {
          await backendRepository.approve(approval.id);
        } else {
          await backendRepository.reject(approval.id);
        }
        // The worker resumes/blocks the real execution; the connected task's
        // SSE subscription (useConnectedTask) reflects the resulting state.
        // Reflect the decision locally too so the panel updates immediately.
        resolveApproval(approval.id, status);
      } else {
        resolveApproval(approval.id, status);
        setTaskStatus(approval.taskId, status === "APPROVED" ? "RUNNING" : "FAILED");
      }
      onResolved?.(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record the decision.");
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 space-y-5">
        <div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-2xs uppercase tracking-wider text-muted-foreground">
              {pending ? "Approval required" : "Approval"}
            </span>
            <ApprovalStatusBadge status={approval.status} size="sm" />
          </div>
          <h2 className={compact ? "mt-1 text-base font-semibold" : "mt-1 text-lg font-semibold"}>
            {approval.action}
          </h2>
          <Link
            href={`/tasks/${approval.taskId}`}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
          >
            {approval.taskName}
          </Link>
        </div>

        <div className="rounded-lg border border-border">
          <div className="px-4 py-2">
            {approval.target && <MetaRow label="Target">{approval.target}</MetaRow>}
            {approval.attachment && (
              <MetaRow label="Attachment" mono>
                {approval.attachment}
              </MetaRow>
            )}
            <MetaRow label="Category">{approval.category}</MetaRow>
            <MetaRow label="Risk">{approval.risk}</MetaRow>
            <MetaRow label="Plan">{approval.planLabel}</MetaRow>
            <MetaRow label="Requested">
              {relativeTime(approval.requestedAt)}
            </MetaRow>
          </div>
        </div>

        <div>
          <p className="mb-2 text-2xs uppercase tracking-wider text-muted-foreground">
            Evidence
          </p>
          <ul className="space-y-1.5">
            {approval.evidence.map((e) => (
              <li
                key={e.id}
                className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
              >
                <span
                  className="flex size-4 items-center justify-center font-mono text-xs"
                  aria-hidden
                >
                  {e.passed ? "✓" : "×"}
                </span>
                <span className={e.passed ? "" : "text-muted-foreground"}>
                  {e.label}
                </span>
                <span className="ml-auto text-2xs text-muted-foreground">
                  {e.passed ? "Passed" : "Failed"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {pending ? (
        <>
          <Separator className="my-4" />
          {error && (
            <p className="mb-2 text-xs text-destructive" role="alert">
              {error}
            </p>
          )}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              className="flex-1"
              disabled={submitting !== null}
              onClick={() => void decide("REJECTED")}
            >
              <X /> {submitting === "REJECTED" ? "Rejecting…" : "Reject"}
            </Button>
            <Button
              className="flex-1"
              disabled={submitting !== null}
              onClick={() => void decide("APPROVED")}
            >
              <Check /> {submitting === "APPROVED" ? "Approving…" : "Approve"}
            </Button>
          </div>
        </>
      ) : (
        <>
          <Separator className="my-4" />
          <p className="text-center text-xs text-muted-foreground">
            {approval.status === "APPROVED"
              ? "Approved"
              : approval.status === "REJECTED"
                ? "Rejected — no external action was performed."
                : "This approval window has passed."}
            {approval.resolvedAt && ` · ${relativeTime(approval.resolvedAt)}`}
          </p>
        </>
      )}
    </div>
  );
}
