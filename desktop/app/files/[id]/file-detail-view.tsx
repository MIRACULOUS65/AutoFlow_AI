"use client";

import Link from "next/link";
import { repository } from "@/lib/repository";
import { kindIcon, kindLabel } from "@/lib/icons";
import { formatBytes, relativeTime } from "@/lib/utils";
import { PageContainer, MetaRow, SectionHeading } from "@/components/shared/page";
import { Icon } from "@/components/shared/icon";
import { EmptyState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";

export function FileDetailView({ id }: { id: string }) {
  const file = repository.file(id);
  const workspace = file ? repository.workspace(file.workspaceId) : undefined;

  if (!file) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState
          icon="SearchX"
          title="File not found"
          action={
            <Button asChild variant="outline">
              <Link href="/files">Back to files</Link>
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
          <Icon name={kindIcon(file.kind)} className="size-5" />
        </div>
        <div className="min-w-0">
          <h1 className="truncate font-mono text-lg font-semibold">
            {file.name}
          </h1>
          <p className="text-sm text-muted-foreground">
            {kindLabel(file.kind)} · {formatBytes(file.sizeBytes)}
          </p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="outline">Open</Button>
          <Button variant="outline">Download</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          <SectionHeading title="Preview" className="mb-3" />
          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-border bg-surface">
            <Icon name={kindIcon(file.kind)} className="size-12 text-muted-foreground" />
          </div>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <SectionHeading title="Metadata" className="mb-2" />
          <MetaRow label="Type">{kindLabel(file.kind)}</MetaRow>
          <MetaRow label="Size">{formatBytes(file.sizeBytes)}</MetaRow>
          <MetaRow label="Owner">{file.owner}</MetaRow>
          <MetaRow label="Workspace">{workspace?.name ?? "—"}</MetaRow>
          <MetaRow label="Path" mono>
            {file.path}
          </MetaRow>
          <MetaRow label="Updated">{relativeTime(file.updatedAt)}</MetaRow>
        </div>
      </div>
    </PageContainer>
  );
}
