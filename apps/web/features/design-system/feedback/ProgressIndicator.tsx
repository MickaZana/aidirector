"use client";

import { cn } from "../utils/cn";

interface ProgressIndicatorProps {
  /** Progress value 0–100. Omit or pass null for indeterminate (animated) mode. */
  progress?: number | null;
  /** Size of the circular indicator */
  size?: "sm" | "md" | "lg" | "xl";
  /** Show the percentage label inside the circle */
  showPercentage?: boolean;
  /** Label for screen readers */
  label?: string;
  className?: string;
}

const SIZE_CONFIG = {
  sm: { dimension: 64, strokeWidth: 4, fontSize: "text-sm" },
  md: { dimension: 96, strokeWidth: 5, fontSize: "text-lg" },
  lg: { dimension: 128, strokeWidth: 6, fontSize: "text-2xl" },
  xl: { dimension: 160, strokeWidth: 8, fontSize: "text-3xl" },
} as const;

/**
 * ProgressIndicator — A circular progress ring.
 *
 * Determinate mode (pass a progress number):
 *   <ProgressIndicator progress={65} />
 *
 * Indeterminate mode (no progress or null):
 *   <ProgressIndicator />  — spinning ring for unknown duration
 *
 * Accessible: announces progress changes for screen readers,
 * respects reduced-motion preferences.
 */
export function ProgressIndicator({
  progress,
  size = "lg",
  showPercentage = true,
  label,
  className,
}: ProgressIndicatorProps) {
  const config = SIZE_CONFIG[size];
  const dimension = config.dimension;
  const stroke = config.strokeWidth;

  const center = dimension / 2;
  const radius = center - stroke / 2;
  const circumference = 2 * Math.PI * radius;

  const isIndeterminate = progress === null || progress === undefined;
  const clampedProgress = Math.min(100, Math.max(0, progress ?? 0));
  const offset = circumference * (1 - clampedProgress / 100);

  const ariaLabel = label ?? (isIndeterminate
    ? "Processing in progress"
    : `Progress: ${Math.round(clampedProgress)} percent`);

  return (
    <div
      className={cn("relative inline-flex items-center justify-center", className)}
      role="progressbar"
      aria-valuenow={isIndeterminate ? undefined : clampedProgress}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel}
    >
      <svg
        width={dimension}
        height={dimension}
        viewBox={`0 0 ${dimension} ${dimension}`}
        className={cn(
          "-rotate-90",
          isIndeterminate && "motion-safe:animate-spin",
        )}
        aria-hidden="true"
      >
        {/* Background track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={stroke}
        />

        {/* Progress arc */}
        {isIndeterminate ? (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            strokeLinecap="round"
            className="text-emerald-500"
            strokeDasharray={`${circumference * 0.3} ${circumference * 0.7}`}
            strokeDashoffset={circumference * 0.15}
          />
        ) : (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            strokeLinecap="round"
            className="text-emerald-500 transition-all duration-500 motion-safe:transition-all motion-safe:duration-500"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{
              transition: "stroke-dashoffset 0.5s ease-out",
            }}
          />
        )}
      </svg>

      {/* Percentage label */}
      {showPercentage && !isIndeterminate && (
        <span
          className={cn(
            "absolute font-semibold text-slate-900",
            config.fontSize,
          )}
          aria-hidden="true"
        >
          {Math.round(clampedProgress)}%
        </span>
      )}

      {/* Indeterminate "..." label */}
      {showPercentage && isIndeterminate && (
        <span
          className={cn(
            "absolute font-semibold text-slate-400",
            config.fontSize,
          )}
          aria-hidden="true"
        >
          ...
        </span>
      )}
    </div>
  );
}
