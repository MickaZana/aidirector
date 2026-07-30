"use client";

import type { ReactNode, ElementType } from "react";
import { cn } from "../utils/cn";

interface EmptyStateProps {
  icon?: ElementType;
  title?: string;
  description?: string;
  /** Optional action button rendered below the text */
  action?: ReactNode;
  className?: string;
}

/**
 * Empty state — shown when there is no content to display.
 * Useful for first-time users and empty lists/sections.
 */
export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center py-16 px-4",
        className,
      )}
    >
      {Icon && (
        <div className="h-16 w-16 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center mb-5">
          <Icon className="h-8 w-8 text-emerald-400" strokeWidth={1.5} />
        </div>
      )}
      {title && (
        <h3 className="text-xl font-semibold text-slate-900">{title}</h3>
      )}
      {description && (
        <p className="mt-1.5 text-sm text-slate-500 max-w-sm">
          {description}
        </p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
