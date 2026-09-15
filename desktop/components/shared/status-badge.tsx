import { cn } from "@/lib/utils";
import {
  AGENT_STATUS,
  APPROVAL_STATUS,
  STEP_STATUS,
  TASK_STATUS,
  VERIFICATION,
  type StatusDescriptor,
  type StatusTone,
} from "@/lib/constants";
import type {
  AgentStatus,
  ApprovalStatus,
  StepStatus,
  TaskStatus,
  VerificationState,
} from "@/lib/types";

/*
 * Monochrome status badge. State is carried entirely by glyph + tone
 * (ink / border / opacity) — never by hue. `pulse` uses a subtle animated
 * dot; `solid` is filled ink; `outline` is a bordered chip; `muted`/`ghost`
 * recede.
 */

const toneClasses: Record<StatusTone, string> = {
  solid: "border-transparent bg-foreground text-background",
  outline: "border-border bg-transparent text-foreground",
  muted: "border-transparent bg-muted text-muted-foreground",
  ghost: "border-transparent bg-transparent text-muted-foreground",
  pulse: "border-foreground/30 bg-transparent text-foreground",
};

export function StatusBadge({
  descriptor,
  className,
  showGlyph = true,
  size = "default",
}: {
  descriptor: StatusDescriptor;
  className?: string;
  showGlyph?: boolean;
  size?: "default" | "sm";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-medium",
        size === "sm" ? "px-1.5 py-0.5 text-2xs" : "px-2 py-0.5 text-xs",
        toneClasses[descriptor.tone],
        className,
      )}
      title={descriptor.description}
    >
      {showGlyph && (
        <span
          aria-hidden
          className={cn(
            "font-mono leading-none",
            descriptor.tone === "pulse" && "animate-pulse-ring",
          )}
        >
          {descriptor.glyph}
        </span>
      )}
      <span>{descriptor.label}</span>
    </span>
  );
}

export function TaskStatusBadge({
  status,
  ...rest
}: { status: TaskStatus } & Omit<
  React.ComponentProps<typeof StatusBadge>,
  "descriptor"
>) {
  return <StatusBadge descriptor={TASK_STATUS[status]} {...rest} />;
}

export function StepStatusBadge({
  status,
  ...rest
}: { status: StepStatus } & Omit<
  React.ComponentProps<typeof StatusBadge>,
  "descriptor"
>) {
  return <StatusBadge descriptor={STEP_STATUS[status]} {...rest} />;
}

export function ApprovalStatusBadge({
  status,
  ...rest
}: { status: ApprovalStatus } & Omit<
  React.ComponentProps<typeof StatusBadge>,
  "descriptor"
>) {
  return <StatusBadge descriptor={APPROVAL_STATUS[status]} {...rest} />;
}

export function AgentStatusBadge({
  status,
  ...rest
}: { status: AgentStatus } & Omit<
  React.ComponentProps<typeof StatusBadge>,
  "descriptor"
>) {
  return <StatusBadge descriptor={AGENT_STATUS[status]} {...rest} />;
}

export function VerificationBadge({
  state,
  ...rest
}: { state: VerificationState } & Omit<
  React.ComponentProps<typeof StatusBadge>,
  "descriptor"
>) {
  return <StatusBadge descriptor={VERIFICATION[state]} {...rest} />;
}
