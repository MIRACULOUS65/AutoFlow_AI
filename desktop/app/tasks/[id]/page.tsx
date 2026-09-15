import { taskParams } from "@/lib/static-params";
import { TaskDetailView } from "./task-detail-view";

export function generateStaticParams() {
  return taskParams();
}

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TaskDetailView id={id} />;
}
