"use client";

import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { CommandPalette } from "@/components/layout/command-palette";

/**
 * Persistent three-region desktop shell: sidebar · workspace · (page-owned
 * context panel). The command palette is mounted globally and toggled with
 * Ctrl/Cmd+K. Individual pages compose their own right-hand activity panel
 * where it is meaningful (dashboard, task detail).
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
      <CommandPalette />
    </div>
  );
}
