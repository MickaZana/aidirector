"use client";

import { cn } from "../utils/cn";

type StatusBadgeVariant = "ready" | "processing" | "failed" | "draft";

interface StatusBadgeProps {
  status: StatusBadgeVariant;
  className?: string;
}

const STATUS_CONFIG: Record<
  StatusBadgeVariant,
  { label: string; container: string; dot: string }
> = {
  ready: {
    label: "Ready",
    container: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-500",
  },
  processing: {
    label: "Processing",
    container: "bg-blue-50 text-blue-700 border-blue-200",
    dot: "bg-blue-500",
  },
  failed: {
    label: "Failed",
    container: "bg-red-50 text-red-700 border-red-200",
    dot: "bg-red-500",
  },
  draft: {
    label: "Draft",
    container: "bg-slate-100 text-slate-600 border-slate-200",
    dot: "bg-slate-400",
  },
};

/**
 * StatusBadge — small pill badge showing a processing/status state.
 *
 * Usage:
 *   <StatusBadge status="ready" />
 *   <StatusBadge status="processing" />
 */
export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        config.container,
        className,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
    </span>
  );
}
