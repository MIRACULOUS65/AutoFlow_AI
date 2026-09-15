import { workflowParams } from "@/lib/static-params";
import { WorkflowDetailView } from "./workflow-detail-view";

export function generateStaticParams() {
  return workflowParams();
}

export default async function WorkflowDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <WorkflowDetailView id={id} />;
}
