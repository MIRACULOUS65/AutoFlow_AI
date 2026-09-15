import { knowledgeParams } from "@/lib/static-params";
import { KnowledgeDetailView } from "./knowledge-detail-view";

export function generateStaticParams() {
  return knowledgeParams();
}

export default async function KnowledgeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <KnowledgeDetailView id={id} />;
}
