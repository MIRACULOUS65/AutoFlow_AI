"use client";

import Link from "next/link";
import { BookMarked } from "lucide-react";
import { repository } from "@/lib/repository";
import { formatBytes, relativeTime } from "@/lib/utils";
import { PageContainer, MetaRow, SectionHeading } from "@/components/shared/page";
import { EmptyState } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function KnowledgeDetailView({ id }: { id: string }) {
  const source = repository.knowledgeSource(id);
  const workspace = source ? repository.workspace(source.workspaceId) : undefined;

  if (!source) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon="SearchX"
          title="Source not found"
          action={
            <Button asChild variant="outline">
              <Link href="/knowledge">Back to knowledge</Link>
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <PageContainer>
      <div className="mb-6 flex items-start gap-4">
        <div className="flex size-11 items-center justify-center rounded-lg border border-border bg-surface">
          <BookMarked className="size-5" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">
              {source.title}
            </h1>
            <Badge variant="outline" className="capitalize">
              {source.type}
            </Badge>
          </div>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {source.summary}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          <SectionHeading title="Preview" className="mb-3" />
          <div className="space-y-3 rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
            <p>
              This is a frontend representation of an approved knowledge source.
              In the full AutoFlow platform, agents retrieve verified passages
              from this source with provenance attached to every citation.
            </p>
            <div className="space-y-2">
              <div className="h-2.5 w-full rounded bg-muted" />
              <div className="h-2.5 w-11/12 rounded bg-muted" />
              <div className="h-2.5 w-4/5 rounded bg-muted" />
              <div className="h-2.5 w-full rounded bg-muted" />
              <div className="h-2.5 w-3/4 rounded bg-muted" />
            </div>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <SectionHeading title="Metadata" className="mb-2" />
          <MetaRow label="Type">
            <span className="capitalize">{source.type}</span>
          </MetaRow>
          <MetaRow label="Workspace">{workspace?.name ?? "—"}</MetaRow>
          <MetaRow label="Access">
            <span className="capitalize">{source.access}</span>
          </MetaRow>
          <MetaRow label="Version" mono>
            v{source.version}
          </MetaRow>
          <MetaRow label="Provenance">{source.provenance}</MetaRow>
          <MetaRow label="Size">{formatBytes(source.sizeBytes)}</MetaRow>
          <MetaRow label="Updated">{relativeTime(source.updatedAt)}</MetaRow>
        </div>
      </div>
    </PageContainer>
  );
}
