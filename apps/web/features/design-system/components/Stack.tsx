"use client";

import type { ReactNode } from "react";
import { cn } from "../utils/cn";

type StackDirection = "row" | "column";
type StackAlign = "start" | "center" | "end" | "stretch";
type StackJustify = "start" | "center" | "end" | "between" | "around";
type StackGap = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 | 12 | 16;

interface StackProps {
  children: ReactNode;
  direction?: StackDirection;
  align?: StackAlign;
  justify?: StackJustify;
  gap?: StackGap;
  className?: string;
  /** Whether to wrap on overflow */
  wrap?: boolean;
}

const ALIGN_CLASSES: Record<StackAlign, string> = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
  stretch: "items-stretch",
};

const JUSTIFY_CLASSES: Record<StackJustify, string> = {
  start: "justify-start",
  center: "justify-center",
  end: "justify-end",
  between: "justify-between",
  around: "justify-around",
};

const GAP_CLASSES: Record<StackGap, string> = {
  0: "gap-0",
  1: "gap-1",
  2: "gap-2",
  3: "gap-3",
  4: "gap-4",
  5: "gap-5",
  6: "gap-6",
  8: "gap-8",
  10: "gap-10",
  12: "gap-12",
  16: "gap-16",
};

/**
 * Stack — flexbox layout primitive.
 *
 * Examples:
 *   <Stack gap={4}>                → vertical stack with 16px gap
 *   <Stack direction="row" gap={3}> → horizontal stack with 12px gap
 *   <Stack align="center" justify="between"> → centered, space-between
 */
export function Stack({
  children,
  direction = "column",
  align = "start",
  justify = "start",
  gap = 4,
  className,
  wrap = false,
}: StackProps) {
  return (
    <div
      className={cn(
        "flex",
        direction === "row" ? "flex-row" : "flex-col",
        ALIGN_CLASSES[align],
        JUSTIFY_CLASSES[justify],
        GAP_CLASSES[gap],
        wrap && "flex-wrap",
        className,
      )}
    >
      {children}
    </div>
  );
}
