import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";

/**
 * Standard scrollable page wrapper. Keeps consistent padding and max width and
 * ensures the shell's fixed-height main region scrolls internally.
 */
export function PageContainer({
  children,
  className,
  scroll = true,
}: {
  children: React.ReactNode;
  className?: string;
  scroll?: boolean;
}) {
  if (!scroll) {
    return <div className={cn("h-full", className)}>{children}</div>;
  }
  return (
    <ScrollArea className="h-full">
      <div className={cn("mx-auto w-full max-w-[1400px] p-6", className)}>
        {children}
      </div>
    </ScrollArea>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-start justify-between gap-4 pb-6",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      )}
    </div>
  );
}

export function SectionHeading({
  title,
  action,
  className,
}: {
  title: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center justify-between", className)}>
      <h2 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      {action}
    </div>
  );
}

/** Compact key/value metadata rows. */
export function MetaRow({
  label,
  children,
  mono,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span
        className={cn(
          "min-w-0 truncate text-right text-sm",
          mono && "font-mono text-xs",
        )}
      >
        {children}
      </span>
    </div>
  );
}

/** A single dashboard metric. */
export function Metric({
  label,
  value,
  glyph,
}: {
  label: string;
  value: React.ReactNode;
  glyph?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {glyph && (
          <span className="font-mono text-sm text-muted-foreground">
            {glyph}
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular">{value}</p>
    </div>
  );
}
