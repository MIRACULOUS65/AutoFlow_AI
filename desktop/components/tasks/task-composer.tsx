"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Paperclip } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { useSimStore } from "@/lib/sim-store";
import { repository } from "@/lib/repository";
import { backendRepository, isBackendEnabled } from "@/lib/api";
import { uploadRoster } from "@/lib/api/upload";
import { createTaskFromGoal } from "@/lib/simulation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const SUGGESTIONS = [
  "Prepare this week's operations report from approved data, attach it to an email for finance, and ask me before sending.",
  "Reconcile last month's invoices against the ledger and flag mismatches.",
  "Summarize this quarter's research notes into a shareable brief.",
];

export function TaskComposer() {
  const router = useRouter();
  const [goal, setGoal] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [rosterPath, setRosterPath] = useState<string | null>(null);
  const [rosterName, setRosterName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const setWorkspace = useAppStore((s) => s.setWorkspace);
  const addTask = useAppStore((s) => s.addTask);
  const startSim = useSimStore((s) => s.start);
  const workspaces = repository.workspaces();

  const [submitting, setSubmitting] = useState(false);

  const run = async () => {
    const value = goal.trim();
    if (!value || submitting) return;

    // Connected mode: create the task on the control plane and navigate. The
    // task-detail view subscribes to the real SSE stream via useConnectedTask.
    if (isBackendEnabled()) {
      setSubmitting(true);
      try {
        const { taskId } = await backendRepository.createTask({
          workspaceId: activeWs,
          goal: value,
          ...(rosterPath
            ? { clientMetadata: { roster_path: rosterPath } }
            : {}),
        });
        router.push(`/tasks/${taskId}`);
        return;
      } catch {
        // Fall through to the local simulation if the backend is unreachable,
        // so the composer never dead-ends. (Honest: no fake success — this is a
        // client-side preview until the backend is available.)
      } finally {
        setSubmitting(false);
      }
    }

    // Mock mode (default): local, client-side simulation.
    const task = createTaskFromGoal(value, activeWs);
    addTask(task);
    startSim(task);
    router.push(`/tasks/${task.id}`);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void run();
    }
  };

  const onPickFile = () => fileInputRef.current?.click();

  const onFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    // Reset the input so selecting the same file again re-triggers change.
    e.target.value = "";
    if (!file) return;
    setUploadError(null);
    // Uploading a roster only makes sense in connected mode (the AI/ML server
    // reads the file); in mock mode we just note the attachment.
    if (!isBackendEnabled()) {
      setRosterName(file.name);
      setRosterPath(null);
      return;
    }
    setUploading(true);
    try {
      const { path, name } = await uploadRoster(file);
      setRosterPath(path);
      setRosterName(name);
    } catch (err) {
      setRosterPath(null);
      setRosterName(null);
      setUploadError(err instanceof Error ? err.message : "upload failed");
    } finally {
      setUploading(false);
    }
  };

  const clearFile = () => {
    setRosterPath(null);
    setRosterName(null);
    setUploadError(null);
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card">
      <div className="af-grid pointer-events-none absolute inset-0 opacity-[0.35]" />
      <div className="relative p-5">
        <label
          htmlFor="composer"
          className="text-sm font-medium text-muted-foreground"
        >
          What do you want AutoFlow to do?
        </label>
        <Textarea
          id="composer"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={onKeyDown}
          rows={3}
          placeholder="Describe a goal in plain language. AutoFlow will plan the workflow, assign agents, and ask before any external action."
          className="mt-2 resize-none border-0 bg-transparent px-0 text-base shadow-none focus-visible:ring-0"
        />

        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              className="hidden"
              onChange={(e) => void onFileChange(e)}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={rosterName ? clearFile : onPickFile}
              disabled={uploading}
              className={cn(rosterName && "border-foreground")}
              title={rosterName ? `Attached: ${rosterName} (click to remove)` : "Attach an employee roster (.xlsx)"}
            >
              <Paperclip />
              {uploading
                ? "Uploading…"
                : rosterName
                  ? `${rosterName.length > 22 ? rosterName.slice(0, 22) + "…" : rosterName} ✕`
                  : "Attach file"}
            </Button>
            <Select value={activeWs} onValueChange={setWorkspace}>
              <SelectTrigger className="h-8 w-auto gap-2 border-border text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {workspaces.map((w) => (
                  <SelectItem key={w.id} value={w.id}>
                    {w.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => void run()} disabled={!goal.trim() || submitting}>
            {submitting ? "Starting…" : "Run Task"}
            <ArrowRight />
          </Button>
        </div>
        {uploadError && (
          <p className="mt-2 text-2xs text-destructive">
            Attachment upload failed: {uploadError}
          </p>
        )}
      </div>

      <div className="relative flex flex-wrap gap-2 border-t border-border bg-surface/60 px-5 py-3">
        <span className="text-2xs uppercase tracking-wider text-muted-foreground">
          Try
        </span>
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => setGoal(s)}
            className="max-w-full truncate rounded-md border border-border bg-background px-2 py-1 text-2xs text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
          >
            {s.length > 52 ? `${s.slice(0, 52)}…` : s}
          </button>
        ))}
      </div>
    </div>
  );
}
