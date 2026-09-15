"use client";

import Link from "next/link";
import { BookMarked, Lock, Building2, Users } from "lucide-react";
import type { AccessScope, KnowledgeSource } from "@/lib/types";
import { formatBytes, relativeTime } from "@/lib/utils";

const ACCESS_ICON: Record<AccessScope, typeof Lock> = {
  restricted: Lock,
  organization: Building2,
  workspace: Users,
};

export function KnowledgeRow({ source }: { source: KnowledgeSource }) {
  const AccessIcon = ACCESS_ICON[source.access];
  return (
    <Link
      href={`/knowledge/${source.id}`}
      className="group flex items-center gap-3 p-4 transition-colors hover:bg-accent/40"
    >
      <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-surface">
        <BookMarked className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium group-hover:underline">
          {source.title}
        </p>
        <p className="truncate text-2xs text-muted-foreground">
          {source.summary}
        </p>
      </div>
      <span className="hidden items-center gap-1 text-2xs capitalize text-muted-foreground sm:flex">
        <AccessIcon className="size-3" />
        {source.access}
      </span>
      <span className="hidden font-mono text-2xs text-muted-foreground md:block">
        v{source.version}
      </span>
      <span className="hidden text-2xs tabular text-muted-foreground lg:block">
        {formatBytes(source.sizeBytes)}
      </span>
      <span className="w-20 shrink-0 text-right text-2xs tabular text-muted-foreground">
        {relativeTime(source.updatedAt)}
      </span>
    </Link>
  );
}
