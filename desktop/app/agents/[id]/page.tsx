import { agentParams } from "@/lib/static-params";
import { AgentDetailView } from "./agent-detail-view";

export function generateStaticParams() {
  return agentParams();
}

export default async function AgentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AgentDetailView id={id} />;
}
