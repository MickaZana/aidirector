import * as React from "react";
import { cn } from "@/lib/cn";

type SurfaceVariant = "panel" | "card" | "elevated" | "glass";

interface SurfaceProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: SurfaceVariant;
  /** Add hover depth on cards. Use sparingly. */
  interactive?: boolean;
  /** Tighter padding for sub-cards inside a feature surface. */
  dense?: boolean;
}

const VARIANT_CLASSES: Record<SurfaceVariant, string> = {
  panel: "bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)]",
  card: "bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] rounded-2xl shadow-[var(--shadow-card)]",
  elevated:
    "bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-strong)] rounded-2xl shadow-[var(--shadow-elevated)]",
  glass:
    "bg-[color:var(--color-surface-glass)] backdrop-blur-xl border border-[color:var(--color-border-soft)] rounded-2xl",
};

/**
 * Base surface primitive. Every panel, card, modal, sidebar uses this so
 * the cinematic dark glossy aesthetic stays consistent.
 */
export const Surface = React.forwardRef<HTMLDivElement, SurfaceProps>(
  ({ variant = "card", interactive, dense, className, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn(
        VARIANT_CLASSES[variant],
        dense ? "p-4" : "p-6",
        interactive &&
          "transition-shadow duration-[var(--motion-default)] ease-[cubic-bezier(0.2,0.8,0.2,1)] hover:shadow-[var(--shadow-card-hover)] hover:border-[color:var(--color-border-accent)]",
        className,
      )}
      {...rest}
    />
  ),
);
Surface.displayName = "Surface";
