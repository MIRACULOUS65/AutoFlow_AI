"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Activity,
  BadgeCheck,
  Bot,
  BookMarked,
  FileBox,
  FolderClosed,
  LayoutDashboard,
  ListChecks,
  Workflow,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";

const NAV = [
  { label: "Home", href: "/", icon: LayoutDashboard },
  { label: "Tasks", href: "/tasks", icon: ListChecks },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Workflows", href: "/workflows", icon: Workflow },
  { label: "Knowledge", href: "/knowledge", icon: BookMarked },
  { label: "Files", href: "/files", icon: FolderClosed },
  { label: "Approvals", href: "/approvals", icon: BadgeCheck },
  { label: "Executions", href: "/executions", icon: Activity },
];

export function CommandPalette() {
  const open = useAppStore((s) => s.commandOpen);
  const setOpen = useAppStore((s) => s.setCommandOpen);
  const toggle = useAppStore((s) => s.toggleCommand);
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        toggle();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [toggle]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  const tasks = repository.tasks(activeWs).slice(0, 6);
  const agents = repository.agents().slice(0, 6);
  const workflows = repository.workflows(activeWs);
  const executions = repository.executions(activeWs).slice(0, 6);
  const artifacts = repository.artifacts(activeWs).slice(0, 6);
  const knowledge = repository.knowledge(activeWs).slice(0, 6);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search tasks, agents, workflows, files…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigate">
          {NAV.map((n) => (
            <CommandItem
              key={n.href}
              value={`nav ${n.label}`}
              onSelect={() => go(n.href)}
            >
              <n.icon className="text-muted-foreground" />
              {n.label}
              <CommandShortcut>Go</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Tasks">
          {tasks.map((t) => (
            <CommandItem
              key={t.id}
              value={`task ${t.name} ${t.id}`}
              onSelect={() => go(`/tasks/${t.id}`)}
            >
              <ListChecks className="text-muted-foreground" />
              <span className="truncate">{t.name}</span>
              <CommandShortcut className="font-mono">
                {t.status}
              </CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandGroup heading="Agents">
          {agents.map((a) => (
            <CommandItem
              key={a.id}
              value={`agent ${a.name}`}
              onSelect={() => go(`/agents/${a.id}`)}
            >
              <Bot className="text-muted-foreground" />
              <span className="truncate">{a.name}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandGroup heading="Workflows">
          {workflows.map((w) => (
            <CommandItem
              key={w.id}
              value={`workflow ${w.name}`}
              onSelect={() => go(`/workflows/${w.id}`)}
            >
              <Workflow className="text-muted-foreground" />
              <span className="truncate">{w.name}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandGroup heading="Executions">
          {executions.map((e) => (
            <CommandItem
              key={e.id}
              value={`execution ${e.id} ${e.taskName}`}
              onSelect={() => go(`/executions/${e.id}`)}
            >
              <Activity className="text-muted-foreground" />
              <span className="truncate font-mono text-xs">{e.id}</span>
              <span className="truncate text-muted-foreground">
                {e.taskName}
              </span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandGroup heading="Knowledge">
          {knowledge.map((k) => (
            <CommandItem
              key={k.id}
              value={`knowledge ${k.title}`}
              onSelect={() => go(`/knowledge/${k.id}`)}
            >
              <BookMarked className="text-muted-foreground" />
              <span className="truncate">{k.title}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandGroup heading="Artifacts">
          {artifacts.map((a) => (
            <CommandItem
              key={a.id}
              value={`artifact ${a.name}`}
              onSelect={() => go(`/files`)}
            >
              <FileBox className="text-muted-foreground" />
              <span className="truncate font-mono text-xs">{a.name}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
