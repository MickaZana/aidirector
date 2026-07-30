"use client";

import type { ReactNode } from "react";
import { cn } from "../utils/cn";

interface PageContainerProps {
  children: ReactNode;
  className?: string;
  /** Maximum width (defaults to 1100px per spec) */
  maxWidth?: string;
}

/**
 * PageContainer — centered page wrapper with max-width constraint.
 * All creator screens should use this as their root layout.
 *
 * Default: max-w-[1100px], centered, responsive padding.
 */
export function PageContainer({
  children,
  className,
  maxWidth = "1100px",
}: PageContainerProps) {
  return (
    <div className="bg-[#F8FAFC] min-h-screen">
      <div
        className={cn(
          "mx-auto px-6 py-12 md:py-16",
          className,
        )}
        style={{ maxWidth }}
      >
        {children}
      </div>
    </div>
  );
}
