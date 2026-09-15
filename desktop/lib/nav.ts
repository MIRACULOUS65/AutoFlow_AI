import { repository } from "@/lib/repository";

/** Segment → display label for breadcrumbs / top-bar title. */
const SEGMENT_LABEL: Record<string, string> = {
  "": "Home",
  tasks: "Tasks",
  agents: "Agents",
  workflows: "Workflows",
  knowledge: "Knowledge",
  files: "Files",
  approvals: "Approvals",
  executions: "Executions",
  settings: "Settings",
};

/** Resolve a human label for a dynamic id segment where possible. */
function resolveIdLabel(parent: string, id: string): string {
  switch (parent) {
    case "tasks":
      return repository.task(id)?.name ?? id;
    case "agents":
      return repository.agent(id)?.name ?? id;
    case "workflows":
      return repository.workflow(id)?.name ?? id;
    case "executions":
      return repository.execution(id)?.id ?? id;
    case "knowledge":
      return repository.knowledgeSource(id)?.title ?? id;
    case "files":
      return repository.file(id)?.name ?? id;
    default:
      return id;
  }
}

export interface Crumb {
  label: string;
  href: string;
  current: boolean;
}

export function buildBreadcrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) {
    return [{ label: "Home", href: "/", current: true }];
  }

  const crumbs: Crumb[] = [];
  let href = "";
  segments.forEach((seg, i) => {
    href += `/${seg}`;
    const parent = i > 0 ? segments[i - 1] : "";
    const label =
      SEGMENT_LABEL[seg] ??
      (parent ? resolveIdLabel(parent, seg) : seg);
    crumbs.push({ label, href, current: i === segments.length - 1 });
  });
  return crumbs;
}

export function pageTitle(pathname: string): string {
  const crumbs = buildBreadcrumbs(pathname);
  return crumbs[crumbs.length - 1]?.label ?? "AutoFlow";
}
