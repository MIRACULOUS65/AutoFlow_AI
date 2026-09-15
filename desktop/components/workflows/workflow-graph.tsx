"use client";

/**
 * Compact linear workflow graph rendered from step titles. Monochrome nodes
 * connected by simple connectors — represents the reusable workflow shape.
 */
export function WorkflowGraph({ steps }: { steps: string[] }) {
  return (
    <div className="flex flex-col gap-0">
      {steps.map((title, i) => (
        <div key={i} className="flex flex-col items-start">
          <div className="flex w-full items-center gap-3 rounded-md border border-border bg-card px-3 py-2.5">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-md border border-border font-mono text-2xs tabular">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="text-sm">{title}</span>
          </div>
          {i < steps.length - 1 && (
            <span className="ml-6 h-4 w-px bg-border" aria-hidden />
          )}
        </div>
      ))}
    </div>
  );
}
