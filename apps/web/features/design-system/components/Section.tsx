"use client";

import type { ReactNode } from "react";
import { cn } from "../utils/cn";

interface SectionProps {
  children: ReactNode;
  title?: string;
  description?: string;
  className?: string;
  /** Accessible id for the section */
  id?: string;
}

/**
 * Section — a page section with optional title and description.
 * Provides consistent vertical spacing.
 */
export function Section({
  children,
  title,
  description,
  className,
  id,
}: SectionProps) {
  return (
    <section id={id} className={cn("space-y-6", className)}>
      {title && (
        <div className="space-y-1">
          <h2 className="text-[30px] font-bold leading-[1.2] tracking-tight text-slate-900">
            {title}
          </h2>
          {description && (
            <p className="text-base text-slate-500">{description}</p>
          )}
        </div>
      )}
      {children}
    </section>
  );
}
