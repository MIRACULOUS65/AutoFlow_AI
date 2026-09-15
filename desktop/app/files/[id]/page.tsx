import { fileParams } from "@/lib/static-params";
import { FileDetailView } from "./file-detail-view";

export function generateStaticParams() {
  return fileParams();
}

export default async function FileDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <FileDetailView id={id} />;
}
