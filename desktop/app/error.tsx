"use client";

import { useEffect } from "react";
import { ErrorState } from "@/components/shared/states";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface for debugging; no external reporting in this build.
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-full items-center justify-center p-6">
      <ErrorState
        title="Something went wrong"
        description="AutoFlow could not load this view."
        onRetry={reset}
        className="max-w-md"
      />
    </div>
  );
}
