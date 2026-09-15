"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function WorkspaceSelector({ collapsed }: { collapsed?: boolean }) {
  const activeId = useAppStore((s) => s.activeWorkspaceId);
  const setWorkspace = useAppStore((s) => s.setWorkspace);
  const workspaces = repository.workspaces();
  const active = workspaces.find((w) => w.id === activeId) ?? workspaces[0];

  const glyph = active.name.slice(0, 1).toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "af-no-drag flex w-full items-center gap-2.5 rounded-md border border-border bg-card px-2 py-1.5 text-left transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            collapsed && "justify-center px-0",
          )}
          aria-label="Switch workspace"
        >
          <span className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border bg-background font-mono text-xs font-semibold">
            {glyph}
          </span>
          {!collapsed && (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium leading-tight">
                  {active.name}
                </span>
                {active.members > 0 && (
                  <span className="block truncate text-2xs text-muted-foreground">
                    {active.members} members
                  </span>
                )}
              </span>
              <ChevronsUpDown className="size-3.5 shrink-0 text-muted-foreground" />
            </>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-60">
        <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {workspaces.map((ws) => (
          <DropdownMenuItem
            key={ws.id}
            onSelect={() => setWorkspace(ws.id)}
            className="gap-2.5"
          >
            <span className="flex size-6 items-center justify-center rounded border border-border bg-background font-mono text-2xs font-semibold">
              {ws.name.slice(0, 1)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{ws.name}</span>
              <span className="block truncate text-2xs text-muted-foreground">
                {ws.description}
              </span>
            </span>
            {ws.id === active.id && <Check className="size-4 shrink-0" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
