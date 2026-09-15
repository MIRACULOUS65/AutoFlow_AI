"use client";

import { create } from "zustand";
import type { ExecutionEvent, Task, TaskStep } from "@/lib/types";
import {
  buildResumeScript,
  buildScript,
  type SimFrame,
} from "@/lib/simulation";
import { useAppStore } from "@/lib/store";

/**
 * Drives a mock execution for a single task at a time. Frames are applied on a
 * timer; each frame patches the task (in the main store), appends a live event,
 * and updates the current status message. The player pauses on approval and
 * resumes when the user approves.
 */

interface SimState {
  activeTaskId: string | null;
  running: boolean;
  message: string;
  events: ExecutionEvent[];
  liveSteps: TaskStep[];
  _timer: ReturnType<typeof setTimeout> | null;

  start: (task: Task) => void;
  resume: (task: Task) => void;
  stop: () => void;
  reset: () => void;
}

function playFrames(
  frames: SimFrame[],
  taskId: string,
  set: (partial: Partial<SimState>) => void,
  get: () => SimState,
) {
  let i = 0;

  const step = () => {
    if (i >= frames.length) {
      set({ running: false, _timer: null });
      return;
    }
    const frame = frames[i];
    i += 1;

    const app = useAppStore.getState();

    // Apply status + step patch to the main task store.
    const patch: Partial<Task> = { status: frame.status };
    if (frame.currentStepId) patch.currentStepId = frame.currentStepId;
    app.updateTask(taskId, patch);

    if (frame.patchStep) {
      const task = useAppStore
        .getState()
        .tasks.find((t) => t.id === taskId);
      if (task) {
        const steps = task.steps.map((s) =>
          s.id === frame.patchStep!.id
            ? { ...s, ...frame.patchStep!.changes }
            : s,
        );
        app.updateTask(taskId, { steps });
        set({ liveSteps: steps });
      }
    }

    const nextEvents = frame.event
      ? [...get().events, frame.event]
      : get().events;
    set({ message: frame.message, events: nextEvents });

    if (frame.delay <= 0) {
      // Pause (e.g. approval) — stop the player but keep state.
      set({ running: false, _timer: null });
      return;
    }
    const timer = setTimeout(step, frame.delay);
    set({ _timer: timer });
  };

  step();
}

export const useSimStore = create<SimState>((set, get) => ({
  activeTaskId: null,
  running: false,
  message: "",
  events: [],
  liveSteps: [],
  _timer: null,

  start: (task) => {
    const prev = get()._timer;
    if (prev) clearTimeout(prev);
    set({
      activeTaskId: task.id,
      running: true,
      message: "Planning…",
      events: [],
      liveSteps: task.steps,
    });
    playFrames(buildScript(task), task.id, set, get);
  },

  resume: (task) => {
    const prev = get()._timer;
    if (prev) clearTimeout(prev);
    set({ activeTaskId: task.id, running: true });
    playFrames(buildResumeScript(task), task.id, set, get);
  },

  stop: () => {
    const timer = get()._timer;
    if (timer) clearTimeout(timer);
    set({ running: false, _timer: null });
  },

  reset: () => {
    const timer = get()._timer;
    if (timer) clearTimeout(timer);
    set({
      activeTaskId: null,
      running: false,
      message: "",
      events: [],
      liveSteps: [],
      _timer: null,
    });
  },
}));
