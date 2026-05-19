import * as React from "react";
import { cn } from "@/lib/cn";
import type { StatusKey } from "./tokens";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Status token from the design tokens. */
  status?: StatusKey;
  /** Tone for non-status badges. */
  tone?: "neutral" | "accent" | "warning" | "muted";
  /** Pulse the badge — used for active states. */
  pulse?: boolean;
}

const STATUS_BG: Record<StatusKey, string> = {
  queued: "bg-[color:var(--color-status-queued)]/10 text-[color:var(--color-status-queued)] ring-1 ring-[color:var(--color-status-queued)]/20",
  running: "bg-[color:var(--color-status-running)]/10 text-[color:var(--color-status-running)] ring-1 ring-[color:var(--color-status-running)]/30",
  succeeded: "bg-[color:var(--color-status-succeeded)]/10 text-[color:var(--color-status-succeeded)] ring-1 ring-[color:var(--color-status-succeeded)]/30",
  failed: "bg-[color:var(--color-status-failed)]/10 text-[color:var(--color-status-failed)] ring-1 ring-[color:var(--color-status-failed)]/30",
  warning: "bg-[color:var(--color-status-warning)]/10 text-[color:var(--color-status-warning)] ring-1 ring-[color:var(--color-status-warning)]/30",
  fresh: "bg-[color:var(--color-status-fresh)]/10 text-[color:var(--color-status-fresh)] ring-1 ring-[color:var(--color-status-fresh)]/20",
  maturing: "bg-[color:var(--color-status-maturing)]/10 text-[color:var(--color-status-maturing)] ring-1 ring-[color:var(--color-status-maturing)]/30",
  stable: "bg-[color:var(--color-status-stable)]/10 text-[color:var(--color-status-stable)] ring-1 ring-[color:var(--color-status-stable)]/30",
  decayed: "bg-[color:var(--color-status-decayed)]/10 text-[color:var(--color-status-decayed)] ring-1 ring-[color:var(--color-status-decayed)]/20",
};

const TONE_BG = {
  neutral: "bg-[color:var(--color-surface-2)] text-[color:var(--color-text-secondary)] ring-1 ring-[color:var(--color-border-soft)]",
  accent: "bg-[color:var(--color-accent-green)]/10 text-[color:var(--color-accent-green)] ring-1 ring-[color:var(--color-accent-green)]/30",
  warning: "bg-[color:var(--color-accent-gold)]/10 text-[color:var(--color-accent-gold)] ring-1 ring-[color:var(--color-accent-gold)]/30",
  muted: "bg-[color:var(--color-surface-1)] text-[color:var(--color-text-tertiary)] ring-1 ring-[color:var(--color-border-soft)]",
};

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ status, tone = "neutral", pulse, className, children, ...rest }, ref) => (
    <span
      ref={ref}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium tracking-wide uppercase",
        status ? STATUS_BG[status] : TONE_BG[tone],
        className,
      )}
      {...rest}
    >
      {pulse && (
        <span
          aria-hidden
          className={cn(
            "relative inline-flex h-1.5 w-1.5 rounded-full",
            status === "running" || status === "queued"
              ? "bg-current"
              : "bg-current",
          )}
        >
          <span className="absolute inset-0 rounded-full bg-current opacity-60 animate-ping" />
        </span>
      )}
      {children}
    </span>
  ),
);
Badge.displayName = "Badge";
