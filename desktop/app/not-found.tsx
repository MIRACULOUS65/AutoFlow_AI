import Link from "next/link";
import { EmptyState } from "@/components/shared/states";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <EmptyState
        icon="SearchX"
        title="Page not found"
        description="This view does not exist or has moved."
        action={
          <Button asChild variant="outline">
            <Link href="/">Back to workspace</Link>
          </Button>
        }
        className="max-w-md"
      />
    </div>
  );
}
