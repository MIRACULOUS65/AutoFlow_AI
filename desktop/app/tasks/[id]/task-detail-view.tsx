"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { TaskStep } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { useSimStore } from "@/lib/sim-store";
import { repository } from "@/lib/repository";
import { useConnectedTask } from "@/hooks/use-connected-task";
import { TaskHeader } from "@/components/tasks/task-header";
import { TaskConversationRail } from "@/components/tasks/task-conversation-rail";
import { LiveStage } from "@/components/tasks/live-stage";
import { StepDetail } from "@/components/tasks/step-detail";
import { DetailDrawer } from "@/components/shared/detail-drawer";
import { EmptyState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";

export function TaskDetailView({ id }: { id: string }) {
  const tasks = useAppStore((s) => s.tasks);
  const approvals = useAppStore((s) => s.approvals);
  const simMessage = useSimStore((s) => s.message);
  const simActiveId = useSimStore((s) => s.activeTaskId);
  const simEvents = useSimStore((s) => s.events);
  const resume = useSimStore((s) => s.resume);

  // Connected mode: load the real task + subscribe to live SSE (no-op on mock).
  useConnectedTask(id);

  const task = tasks.find((t) => t.id === id);
  const [selectedStep, setSelectedStep] = useState<TaskStep | null>(null);

  const execution = task?.executionId
    ? repository.execution(task.executionId)
    : undefined;

  const timeline = useMemo(() => {
    // Connected mode feeds live backend events onto the task itself.
    if (task?.liveEvents && task.liveEvents.length > 0) {
      return task.liveEvents;
    }
    const base = execution?.events ?? [];
    if (simActiveId === id && simEvents.length > 0) {
      return [...base, ...simEvents];
    }
    return base;
  }, [task?.liveEvents, execution, simActiveId, id, simEvents]);

  const approval = task
    ? approvals.find((a) => a.taskId === task.id && a.status === "PENDING") ??
      (task.approvalIds[0]
        ? approvals.find((a) => a.id === task.approvalIds[0])
        : undefined)
    : undefined;

  const recoveryStep = task?.steps.find((s) => s.status === "RECOVERY");

  if (!task) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon="SearchX"
          title="Task not found"
          description="This task may have been removed or the link is out of date."
          action={
            <Button asChild variant="outline">
              <Link href="/tasks">Back to tasks</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const message = simActiveId === task.id ? simMessage : undefined;

  return (
    <div className="flex h-full flex-col">
      <TaskHeader task={task} />

      {/* Left: agentic conversation rail (structure kept).
          Center: live working stage (clear until execution starts). */}
      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[380px_1fr]">
        <TaskConversationRail
          task={task}
          message={message}
          approval={approval}
          recoveryStep={recoveryStep}
          onApprovalResolved={(status) => {
            if (status === "APPROVED") resume(task);
          }}
          onSelectStep={setSelectedStep}
        />

        <div className="hidden min-h-0 lg:block">
          <LiveStage
            task={task}
            timeline={timeline}
            message={message}
            selectedStepId={selectedStep?.id}
            onSelectStep={setSelectedStep}
          />
        </div>
      </div>

      {/* Step detail drawer */}
      <DetailDrawer
        open={!!selectedStep}
        onOpenChange={(v) => !v && setSelectedStep(null)}
        eyebrow={selectedStep ? `Step ${selectedStep.index}` : undefined}
        title={selectedStep?.title ?? ""}
        description={selectedStep ? selectedStep.currentState : undefined}
      >
        {selectedStep && <StepDetail step={selectedStep} allSteps={task.steps} />}
      </DetailDrawer>
    </div>
  );
}
