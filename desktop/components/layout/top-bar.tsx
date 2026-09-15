"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, LogOut, Search, Settings, User } from "lucide-react";
import { buildBreadcrumbs } from "@/lib/nav";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { initials } from "@/lib/utils";
import { useDesktop } from "@/hooks/use-desktop";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function TopBar() {
  const pathname = usePathname();
  const crumbs = buildBreadcrumbs(pathname);
  const setCommandOpen = useAppStore((s) => s.setCommandOpen);
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const user = repository.currentUser;
  const { isDesktop } = useDesktop();

  const running = repository
    .executions(activeWs)
    .filter((e) => e.status === "RUNNING" || e.status === "RECOVERY").length;

  const shortcut = isDesktop ? "Ctrl K" : "⌘K";

  return (
    <TooltipProvider delayDuration={200}>
      <header className="af-drag flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background px-4">
        {/* Breadcrumbs */}
        <div className="af-no-drag min-w-0 flex-1">
          <Breadcrumb>
            <BreadcrumbList>
              {crumbs.map((c) => (
                <BreadcrumbItem key={c.href}>
                  {c.current ? (
                    <BreadcrumbPage className="truncate">
                      {c.label}
                    </BreadcrumbPage>
                  ) : (
                    <>
                      <BreadcrumbLink asChild>
                        <Link href={c.href}>{c.label}</Link>
                      </BreadcrumbLink>
                      <BreadcrumbSeparator />
                    </>
                  )}
                </BreadcrumbItem>
              ))}
            </BreadcrumbList>
          </Breadcrumb>
        </div>

        {/* Search / command trigger */}
        <button
          onClick={() => setCommandOpen(true)}
          className="af-no-drag flex h-8 w-64 items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-sm text-muted-foreground transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <Search className="size-4" />
          <span className="flex-1 text-left">Search AutoFlow</span>
          <kbd className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-2xs">
            {shortcut}
          </kbd>
        </button>

        {/* Activity indicator */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Link
              href="/executions"
              className="af-no-drag flex h-8 items-center gap-2 rounded-md border border-border px-2.5 text-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              <span className="relative flex size-2 items-center justify-center">
                <span className="absolute inline-flex size-2 rounded-full bg-foreground/40 animate-ping" />
                <span className="relative inline-flex size-1.5 rounded-full bg-foreground" />
              </span>
              <span className="tabular">{running}</span>
              <Activity className="size-4 text-muted-foreground" />
            </Link>
          </TooltipTrigger>
          <TooltipContent>{running} active executions</TooltipContent>
        </Tooltip>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="af-no-drag flex size-8 items-center justify-center rounded-md border border-border bg-surface text-xs font-medium transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="Account menu"
            >
              {initials(user.name)}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span className="text-sm font-medium text-foreground">
                  {user.name}
                </span>
                <span className="text-2xs text-muted-foreground">
                  {user.email}
                </span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings">
                <User /> Account
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings">
                <Settings /> Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <LogOut /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </header>
    </TooltipProvider>
  );
}
