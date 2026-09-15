import { executionParams } from "@/lib/static-params";
import { ExecutionDetailView } from "./execution-detail-view";

export function generateStaticParams() {
  return executionParams();
}

export default async function ExecutionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExecutionDetailView id={id} />;
}
