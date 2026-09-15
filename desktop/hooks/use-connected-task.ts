"use client";

/**
 * Connected-mode task hook.
 *
 * When a backend is configured (NEXT_PUBLIC_API_URL set) this hook loads a real
 * task from the control plane and subscribes to its live execution event stream
 * (SSE) with reconnect replay, feeding the SAME app store the UI already reads
 * from. Pages stay unchanged: they render the store; the store is fed by the
 * backend instead of the local simulation.
 *
 * When no backend is configured it is a no-op, so the desktop keeps working on
 * local mock data exactly as before.
 */
import { useEffect } from "react";
import {
  backendRepository,
  isBackendEnabled,
  subscribeToExecutionEvents,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { ExecutionEvent, TaskStatus } from "@/lib/types";

// SSE event types that imply a task-status change we can reflect immediately.
const EVENT_TO_STATUS: Record<string, TaskStatus> = {
  "plan.created": "PLANNING",
  "plan.validated": "VALIDATING",
  "step.started": "RUNNING",
  "approval.requested": "AWAITING_APPROVAL",
  "approval.granted": "RUNNING",
  "approval.rejected": "BLOCKED",
  "execution.completed": "COMPLETE",
  "execution.failed": "FAILED",
  "execution.cancelled": "CANCELLED",
};

export function useConnectedTask(taskId: string): void {
  const upsertTask = useAppStore((s) => s.addTask);
  const updateTask = useAppStore((s) => s.updateTask);
  const setTaskStatus = useAppStore((s) => s.setTaskStatus);
  const upsertApproval = useAppStore((s) => s.upsertApproval);

  useEffect(() => {
    if (!isBackendEnabled() || !taskId) return;

    let cancelled = false;
    let subscription: { close: () => void } | null = null;
    // Accumulate live events so the timeline grows as they arrive.
    const liveEvents: ExecutionEvent[] = [];

    // Load the real pending approval bound to this task (action hash, risk,
    // evidence, expiry) so the approval panel renders real data, not mock.
    const loadPendingApproval = async (id: string) => {
      const approvals = await backendRepository.approvals();
      const pending = approvals.find(
        (a) => a.taskId === id && a.status === "PENDING",
      );
      if (pending && !cancelled) upsertApproval(pending);
    };

    const load = async () => {
      const task = await backendRepository.task(taskId);
      if (cancelled || !task) return;

      // Ensure the task exists in the store, then refresh it with real data.
      const existing = useAppStore.getState().tasks.find((t) => t.id === task.id);
      if (existing) {
        updateTask(task.id, task);
      } else {
        upsertTask(task);
      }

      if (task.status === "AWAITING_APPROVAL") {
        void loadPendingApproval(task.id);
      }

      if (!task.executionId) return;

      // Seed the timeline from any already-persisted events, then tail live.
      const seed = await backendRepository.events(task.executionId, 0);
      if (cancelled) return;
      liveEvents.push(...seed);
      pushTimeline(task.id, liveEvents);

      subscription = subscribeToExecutionEvents(
        task.executionId,
        {
          onEvent: (event) => {
            liveEvents.push(event);
            pushTimeline(task.id, liveEvents);
            const next = EVENT_TO_STATUS[event.type];
            if (next) setTaskStatus(task.id, next);
            if (event.type === "approval.requested") {
              void loadPendingApproval(task.id);
            }
          },
          onEnd: (status) => {
            // Refresh the authoritative task once the stream closes.
            void refresh(task.id);
            const st = status as TaskStatus;
            if (st) setTaskStatus(task.id, st);
          },
        },
        { after: seed.at(-1)?.sequence ?? 0 },
      );
    };

    const refresh = async (id: string) => {
      const fresh = await backendRepository.task(id);
      if (!cancelled && fresh) updateTask(id, fresh);
    };

    const pushTimeline = (id: string, events: ExecutionEvent[]) => {
      updateTask(id, { liveEvents: [...events] });
    };

    void load();

    return () => {
      cancelled = true;
      subscription?.close();
    };
  }, [taskId, upsertTask, updateTask, setTaskStatus, upsertApproval]);
}
