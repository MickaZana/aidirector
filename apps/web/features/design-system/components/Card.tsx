"use client";

import type { ReactNode } from "react";
import { cn } from "../utils/cn";

interface CardProps {
  children: ReactNode;
  className?: string;
  /** Enable hover effect */
  hoverable?: boolean;
  /** Smaller padding variant */
  dense?: boolean;
  onClick?: () => void;
}

/**
 * Card — white rounded-2xl container with border and shadow.
 * The primary surface for grouping content on creator screens.
 *
 * Radius: 16px (rounded-2xl) per spec. White bg, slate-200 border.
 */
export function Card({
  children,
  className,
  hoverable = false,
  dense = false,
  onClick,
}: CardProps) {
  const Component = onClick ? "button" : "div";

  return (
    <Component
      onClick={onClick}
      className={cn(
        "rounded-2xl bg-white border border-slate-200 shadow-sm",
        dense ? "p-4" : "p-6 md:p-8",
        hoverable &&
          "transition-all duration-200 hover:shadow-md hover:border-slate-300",
        onClick && "text-left w-full cursor-pointer",
        className,
      )}
    >
      {children}
    </Component>
  );
}
