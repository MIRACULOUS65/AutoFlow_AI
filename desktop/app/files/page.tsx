"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronRight, Upload } from "lucide-react";
import type { FileItem } from "@/lib/types";
import { useAppStore } from "@/lib/store";
import { repository } from "@/lib/repository";
import { backendRepository } from "@/lib/api";
import { useConnectedList } from "@/hooks/use-connected-list";
import { kindIcon, kindLabel } from "@/lib/icons";
import { formatBytes, relativeTime } from "@/lib/utils";
import { PageContainer, PageHeader, MetaRow } from "@/components/shared/page";
import { SearchField } from "@/components/shared/toolbar";
import { Icon } from "@/components/shared/icon";
import { EmptyState } from "@/components/shared/states";
import { DetailDrawer } from "@/components/shared/detail-drawer";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function FilesPage() {
  const activeWs = useAppStore((s) => s.activeWorkspaceId);
  const [query, setQuery] = useState("");
  const [folder, setFolder] = useState<string | null>(null);
  const [preview, setPreview] = useState<FileItem | null>(null);
  const { items: all } = useConnectedList(
    () => backendRepository.files(activeWs),
    repository.files(activeWs),
    [activeWs],
  );

  const folders = all.filter((f) => f.kind === "folder");
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all
      .filter((f) => f.kind !== "folder")
      .filter((f) => (folder ? f.path === `/${folder}` : true))
      .filter((f) => !q || f.name.toLowerCase().includes(q));
  }, [all, query, folder]);

  return (
    <PageContainer>
      <PageHeader
        title="Files"
        description="Inputs and generated deliverables across this workspace."
        actions={
          <Button variant="outline">
            <Upload /> Upload
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SearchField
          value={query}
          onChange={setQuery}
          placeholder="Search files…"
          className="w-64"
        />
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <button
            onClick={() => setFolder(null)}
            className="hover:text-foreground"
          >
            Files
          </button>
          {folder && (
            <>
              <ChevronRight className="size-3.5" />
              <span className="text-foreground">{folder}</span>
            </>
          )}
        </div>
      </div>

      {/* Folders */}
      {!folder && !query && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {folders.map((f) => (
            <button
              key={f.id}
              onClick={() => setFolder(f.name)}
              className="flex items-center gap-2.5 rounded-lg border border-border bg-card p-3 text-left transition-colors hover:border-foreground/30"
            >
              <Icon name="Folder" className="size-4 shrink-0" />
              <span className="truncate text-sm font-medium">{f.name}</span>
            </button>
          ))}
        </div>
      )}

      {visible.length === 0 ? (
        <EmptyState
          icon="FolderClosed"
          title="No files"
          description="Files in this location will appear here."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Owner</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead className="text-right">Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((f) => (
                <TableRow
                  key={f.id}
                  className="cursor-pointer"
                  onClick={() => setPreview(f)}
                >
                  <TableCell>
                    <span className="flex items-center gap-2.5">
                      <Icon
                        name={kindIcon(f.kind)}
                        className="size-4 shrink-0 text-muted-foreground"
                      />
                      <span className="truncate font-mono text-sm">
                        {f.name}
                      </span>
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {kindLabel(f.kind)}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {f.owner}
                  </TableCell>
                  <TableCell className="text-right text-sm tabular text-muted-foreground">
                    {formatBytes(f.sizeBytes)}
                  </TableCell>
                  <TableCell className="text-right text-sm tabular text-muted-foreground">
                    {relativeTime(f.updatedAt)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <DetailDrawer
        open={!!preview}
        onOpenChange={(v) => !v && setPreview(null)}
        eyebrow={preview ? kindLabel(preview.kind) : undefined}
        title={preview?.name ?? ""}
        footer={
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1">
              Open
            </Button>
            <Button variant="outline" className="flex-1">
              Download
            </Button>
          </div>
        }
      >
        {preview && (
          <div className="space-y-5">
            <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed border-border bg-surface">
              <Icon
                name={kindIcon(preview.kind)}
                className="size-10 text-muted-foreground"
              />
            </div>
            <div className="rounded-lg border border-border px-4 py-2">
              <MetaRow label="Type">{kindLabel(preview.kind)}</MetaRow>
              <MetaRow label="Size">{formatBytes(preview.sizeBytes)}</MetaRow>
              <MetaRow label="Owner">{preview.owner}</MetaRow>
              <MetaRow label="Path" mono>
                {preview.path}
              </MetaRow>
              <MetaRow label="Updated">{relativeTime(preview.updatedAt)}</MetaRow>
            </div>
          </div>
        )}
      </DetailDrawer>
    </PageContainer>
  );
}
