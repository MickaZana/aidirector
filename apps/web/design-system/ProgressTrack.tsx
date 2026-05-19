import * as React from "react";
import { cn } from "@/lib/cn";

interface ProgressTrackProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0..1 */
  value: number;
  /** Bar colour token. Defaults to the accent green. */
  tone?: "accent" | "blue" | "gold" | "magenta" | "neutral";
  /** Show value as text on the right. */
  showValue?: boolean;
  /** Animate the fill in on mount. */
  animate?: boolean;
}

const TONE_BAR: Record<NonNullable<ProgressTrackProps["tone"]>, string> = {
  accent: "bg-gradient-to-r from-[color:var(--color-accent-green-dim)] to-[color:var(--color-accent-green)]",
  blue: "bg-gradient-to-r from-[color:var(--color-accent-blue)]/70 to-[color:var(--color-accent-blue)]",
  gold: "bg-gradient-to-r from-[color:var(--color-accent-gold)]/70 to-[color:var(--color-accent-gold)]",
  magenta: "bg-gradient-to-r from-[color:var(--color-accent-magenta)]/70 to-[color:var(--color-accent-magenta)]",
  neutral: "bg-[color:var(--color-text-tertiary)]",
};

export function ProgressTrack({
  value,
  tone = "accent",
  showValue,
  animate = true,
  className,
  ...rest
}: ProgressTrackProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const pct = `${(clamped * 100).toFixed(1)}%`;
  return (
    <div className={cn("flex items-center gap-3 w-full", className)} {...rest}>
      <div className="flex-1 h-1.5 rounded-full bg-[color:var(--color-surface-3)] overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full",
            TONE_BAR[tone],
            animate &&
              "transition-[width] duration-[var(--motion-slow)] ease-[cubic-bezier(0.2,0.8,0.2,1)]",
          )}
          style={{ width: pct }}
        />
      </div>
      {showValue && (
        <span className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)] tabular-nums">
          {pct}
        </span>
      )}
    </div>
  );
}
