import type { ArtifactKind, FileKind } from "@/lib/types";

/** Artifact/file kind → lucide icon name (resolved via <Icon />). */
export const KIND_ICON: Record<ArtifactKind | FileKind, string> = {
  document: "FileText",
  spreadsheet: "Table2",
  presentation: "Presentation",
  report: "FileBarChart",
  image: "Image",
  code: "FileCode2",
  log: "ScrollText",
  folder: "Folder",
};

export function kindIcon(kind: ArtifactKind | FileKind): string {
  return KIND_ICON[kind] ?? "File";
}

export function kindLabel(kind: ArtifactKind | FileKind): string {
  return kind.charAt(0).toUpperCase() + kind.slice(1);
}
