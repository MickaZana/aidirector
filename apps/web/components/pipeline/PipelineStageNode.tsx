"use client";

import { motion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { StatusDot } from "@/design-system/StatusDot";
import { formatSeconds } from "@/lib/format";
import type { PipelineStage } from "@/lib/api/types";

interface Props {
  stage: PipelineStage;
  index: number;
  isLast: boolean;
}

const STATUS_TO_KEY = {
  idle: "queued",
  queued: "queued",
  running: "running",
  succeeded: "succeeded",
  failed: "failed",
} as const;

export function PipelineStageNode({ stage, index, isLast }: Props) {
  const statusKey = STATUS_TO_KEY[stage.status];
  const isRunning = stage.status === "running";
  const isDone = stage.status === "succeeded";
  const isFailed = stage.status === "failed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.42, delay: index * 0.04, ease: [0.2, 0.8, 0.2, 1] }}
      className="relative flex gap-4"
    >
      {/* Rail */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            "relative h-10 w-10 rounded-xl flex items-center justify-center border transition-colors",
            isDone &&
              "bg-[color:var(--color-accent-green)]/10 border-[color:var(--color-accent-green)]/40",
            isRunning &&
              "bg-[color:var(--color-accent-blue)]/10 border-[color:var(--color-accent-blue)]/40 shadow-[0_0_24px_-6px_rgba(61,169,252,0.6)]",
            isFailed &&
              "bg-[color:var(--color-accent-magenta)]/10 border-[color:var(--color-accent-magenta)]/40",
            !isDone && !isRunning && !isFailed &&
              "bg-[color:var(--color-surface-2)] border-[color:var(--color-border-soft)]",
          )}
        >
          {isDone && <Check className="h-4 w-4 text-[color:var(--color-accent-green)]" strokeWidth={2.5} />}
          {isRunning && <Loader2 className="h-4 w-4 text-[color:var(--color-accent-blue)] animate-spin" strokeWidth={2.5} />}
          {isFailed && <X className="h-4 w-4 text-[color:var(--color-accent-magenta)]" strokeWidth={2.5} />}
          {!isDone && !isRunning && !isFailed && (
            <span className="font-mono text-[10px] tracking-wider text-[color:var(--color-text-tertiary)]">
              {String(index + 1).padStart(2, "0")}
            </span>
          )}
        </div>
        {!isLast && (
          <div
            className={cn(
              "w-px flex-1 my-2 transition-colors",
              isDone
                ? "bg-gradient-to-b from-[color:var(--color-accent-green)]/50 to-[color:var(--color-border-soft)]"
                : "bg-[color:var(--color-border-soft)]",
            )}
          />
        )}
      </div>

      {/* Card */}
      <div className="flex-1 pb-6">
        <div className="flex items-center gap-3 flex-wrap">
          <h3 className="text-sm font-semibold tracking-tight">{stage.label}</h3>
          <span className="text-[11px] uppercase tracking-wider text-[color:var(--color-text-tertiary)] inline-flex items-center gap-1.5">
            <StatusDot status={statusKey} size="sm" pulse={isRunning} />
            {stage.status}
          </span>
          {stage.elapsed_seconds != null && (
            <span className="font-mono text-[11px] text-[color:var(--color-text-tertiary)] tabular-nums">
              {formatSeconds(stage.elapsed_seconds)}
            </span>
          )}
        </div>
        {stage.detail && Object.keys(stage.detail).length > 0 && (
          <pre className="mt-2 rounded-md bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] p-3 text-[11px] font-mono leading-relaxed text-[color:var(--color-text-secondary)] overflow-x-auto">
            {JSON.stringify(stage.detail, null, 2)}
          </pre>
        )}
      </div>
    </motion.div>
  );
}
