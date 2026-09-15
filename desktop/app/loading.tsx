import { PageContainer } from "@/components/shared/page";
import { Skeleton } from "@/components/ui/skeleton";
import { LoadingGrid } from "@/components/shared/states";

export default function Loading() {
  return (
    <PageContainer>
      <div className="mb-6 space-y-2">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-4 w-80" />
      </div>
      <LoadingGrid count={6} />
    </PageContainer>
  );
}
