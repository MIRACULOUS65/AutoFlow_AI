"use client";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";

/**
 * Right-side detail drawer used for graph nodes, files, knowledge sources, etc.
 * Header is fixed; body scrolls.
 */
export function DetailDrawer({
  open,
  onOpenChange,
  title,
  description,
  eyebrow,
  footer,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  eyebrow?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col gap-0 p-0 sm:max-w-md">
        <SheetHeader className="border-b border-border p-5">
          {eyebrow && (
            <div className="mb-1 text-2xs uppercase tracking-wider text-muted-foreground">
              {eyebrow}
            </div>
          )}
          <SheetTitle className="pr-6 text-base">{title}</SheetTitle>
          {description && (
            <SheetDescription>{description}</SheetDescription>
          )}
        </SheetHeader>
        <ScrollArea className="min-h-0 flex-1">
          <div className="p-5">{children}</div>
        </ScrollArea>
        {footer && (
          <div className="border-t border-border p-4">{footer}</div>
        )}
      </SheetContent>
    </Sheet>
  );
}
