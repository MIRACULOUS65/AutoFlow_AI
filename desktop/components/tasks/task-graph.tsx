"use client";

import { useMemo } from "react";
import type { TaskStep } from "@/lib/types";
import { STEP_STATUS } from "@/lib/constants";
import { agentName } from "@/lib/mock-data/agents";
import { cn } from "@/lib/utils";

/*
 * Task graph.
 *
 * Steps are laid out in dependency layers (topological rank). Each node shows
 * step number, title, agent and a monochrome status glyph. Edges are drawn as
 * SVG paths behind the nodes. Nodes are keyboard-focusable buttons; selecting
 * one raises onSelect for the detail drawer.
 */

const NODE_W = 190;
const NODE_H = 74;
const H_GAP = 40;
const V_GAP = 44;
const PAD = 16;

interface Placed {
  step: TaskStep;
  col: number;
  row: number;
  x: number;
  y: number;
}

function layout(steps: TaskStep[]) {
  const byId = new Map(steps.map((s) => [s.id, s]));
  const rank = new Map<string, number>();

  const computeRank = (id: string, seen = new Set<string>()): number => {
    if (rank.has(id)) return rank.get(id)!;
    if (seen.has(id)) return 0;
    seen.add(id);
    const step = byId.get(id);
    if (!step || step.dependsOn.length === 0) {
      rank.set(id, 0);
      return 0;
    }
    const r =
      1 + Math.max(...step.dependsOn.map((d) => computeRank(d, seen)));
    rank.set(id, r);
    return r;
  };
  steps.forEach((s) => computeRank(s.id));

  // Group by rank (column).
  const columns = new Map<number, TaskStep[]>();
  steps.forEach((s) => {
    const r = rank.get(s.id) ?? 0;
    if (!columns.has(r)) columns.set(r, []);
    columns.get(r)!.push(s);
  });

  const placed: Placed[] = [];
  const maxRows = Math.max(...[...columns.values()].map((c) => c.length));
  const totalHeight = maxRows * NODE_H + (maxRows - 1) * V_GAP;

  [...columns.keys()]
    .sort((a, b) => a - b)
    .forEach((col) => {
      const items = columns.get(col)!;
      const colHeight = items.length * NODE_H + (items.length - 1) * V_GAP;
      const offsetY = (totalHeight - colHeight) / 2;
      items
        .sort((a, b) => a.index - b.index)
        .forEach((step, row) => {
          placed.push({
            step,
            col,
            row,
            x: PAD + col * (NODE_W + H_GAP),
            y: PAD + offsetY + row * (NODE_H + V_GAP),
          });
        });
    });

  const cols = columns.size;
  const width = PAD * 2 + cols * NODE_W + (cols - 1) * H_GAP;
  const height = PAD * 2 + totalHeight;
  return { placed, width, height };
}

export function TaskGraph({
  steps,
  selectedId,
  onSelect,
}: {
  steps: TaskStep[];
  selectedId?: string;
  onSelect?: (step: TaskStep) => void;
}) {
  const { placed, width, height } = useMemo(() => layout(steps), [steps]);
  const posById = useMemo(
    () => new Map(placed.map((p) => [p.step.id, p])),
    [placed],
  );

  const edges = placed.flatMap((p) =>
    p.step.dependsOn
      .map((depId) => {
        const from = posById.get(depId);
        if (!from) return null;
        return { from, to: p };
      })
      .filter(Boolean),
  ) as { from: Placed; to: Placed }[];

  return (
    <div className="overflow-auto">
      <div
        className="relative"
        style={{ width, height, minWidth: "100%" }}
      >
        <svg
          className="absolute inset-0 h-full w-full"
          width={width}
          height={height}
          aria-hidden
        >
          {edges.map(({ from, to }, i) => {
            const x1 = from.x + NODE_W;
            const y1 = from.y + NODE_H / 2;
            const x2 = to.x;
            const y2 = to.y + NODE_H / 2;
            const midX = (x1 + x2) / 2;
            const active =
              from.step.status === "COMPLETE" &&
              (to.step.status === "RUNNING" ||
                to.step.status === "COMPLETE" ||
                to.step.status === "VERIFYING" ||
                to.step.status === "APPROVAL");
            return (
              <path
                key={i}
                d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                fill="none"
                stroke="currentColor"
                className={active ? "text-foreground" : "text-border"}
                strokeWidth={active ? 1.5 : 1}
                strokeDasharray={active ? undefined : "3 3"}
              />
            );
          })}
        </svg>

        {placed.map((p) => {
          const desc = STEP_STATUS[p.step.status];
          const selected = p.step.id === selectedId;
          const running = p.step.status === "RUNNING";
          return (
            <button
              key={p.step.id}
              onClick={() => onSelect?.(p.step)}
              className={cn(
                "absolute flex flex-col justify-between rounded-lg border bg-card p-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                selected
                  ? "border-foreground ring-1 ring-foreground"
                  : "border-border hover:border-foreground/40",
                running && "shadow-[0_0_0_1px_hsl(var(--foreground)/0.15)]",
              )}
              style={{
                left: p.x,
                top: p.y,
                width: NODE_W,
                height: NODE_H,
              }}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 truncate">
                  <span className="font-mono text-2xs text-muted-foreground tabular">
                    {String(p.step.index).padStart(2, "0")}
                  </span>
                  <span className="truncate text-sm font-medium">
                    {p.step.title}
                  </span>
                </span>
                <span
                  className={cn(
                    "shrink-0 font-mono text-xs",
                    running && "animate-pulse-ring",
                  )}
                  aria-hidden
                >
                  {desc.glyph}
                </span>
              </div>
              <div className="flex items-center justify-between text-2xs text-muted-foreground">
                <span className="truncate">{agentName(p.step.agentId)}</span>
                <span>{desc.label}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
