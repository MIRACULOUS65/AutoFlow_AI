"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { NAV_GROUPS } from "@/lib/constants";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { cn, initials } from "@/lib/utils";
import { Icon } from "@/components/shared/icon";
import { WorkspaceSelector } from "@/components/layout/workspace-selector";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggle = useAppStore((s) => s.toggleSidebar);
  const user = repository.currentUser;

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "flex h-full flex-col border-r border-border bg-surface transition-[width] duration-200",
          collapsed ? "w-16" : "w-60",
        )}
      >
        {/* Brand */}
        <div
          className={cn(
            "af-drag flex h-14 items-center gap-2.5 border-b border-border px-4",
            collapsed && "justify-center px-0",
          )}
        >
          <div className="af-no-drag flex size-7 items-center justify-center rounded-md bg-foreground text-background">
            <Icon name="Workflow" className="size-4" />
          </div>
          {!collapsed && (
            <span className="text-sm font-semibold tracking-tight">
              AutoFlow
              <span className="ml-1 text-muted-foreground">AI</span>
            </span>
          )}
        </div>

        {/* Workspace */}
        <div className="p-3">
          <WorkspaceSelector collapsed={collapsed} />
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-3">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} className="space-y-0.5">
              {group.label && !collapsed && (
                <p className="px-2 pb-1 pt-1 text-2xs font-medium uppercase tracking-wider text-muted-foreground">
                  {group.label}
                </p>
              )}
              {group.items.map((item) => {
                const active = isActive(pathname, item.href);
                const link = (
                  <Link
                    href={item.href}
                    className={cn(
                      "group relative flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                      active
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:bg-accent hover:text-foreground",
                      collapsed && "justify-center px-0",
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon name={item.icon} className="size-4 shrink-0" />
                    {!collapsed && <span className="flex-1">{item.label}</span>}
                  </Link>
                );

                return collapsed ? (
                  <Tooltip key={item.href}>
                    <TooltipTrigger asChild>{link}</TooltipTrigger>
                    <TooltipContent side="right">{item.label}</TooltipContent>
                  </Tooltip>
                ) : (
                  <div key={item.href}>{link}</div>
                );
              })}
            </div>
          ))}
        </nav>

        {/* User + collapse */}
        <div className="border-t border-border p-3">
          <div
            className={cn(
              "flex items-center gap-2.5",
              collapsed && "flex-col gap-2",
            )}
          >
            <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-border bg-background text-xs font-medium">
              {initials(user.name)}
            </div>
            {!collapsed && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium leading-tight">
                  {user.name}
                </p>
                <p className="truncate text-2xs text-muted-foreground">
                  {user.role}
                </p>
              </div>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={toggle}
                  className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                  {collapsed ? (
                    <PanelLeftOpen className="size-4" />
                  ) : (
                    <PanelLeftClose className="size-4" />
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {collapsed ? "Expand" : "Collapse"}
              </TooltipContent>
            </Tooltip>
          </div>
        </div>
      </aside>
    </TooltipProvider>
  );
}
