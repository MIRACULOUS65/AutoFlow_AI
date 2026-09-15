"use client";

import { icons, type LucideProps } from "lucide-react";

/**
 * Renders a Lucide icon by its string name (as stored in constants).
 * Falls back to a neutral dot if the name is unknown.
 */
export function Icon({
  name,
  ...props
}: { name: string } & LucideProps) {
  const LucideIcon = icons[name as keyof typeof icons] ?? icons.Circle;
  return <LucideIcon {...props} />;
}
