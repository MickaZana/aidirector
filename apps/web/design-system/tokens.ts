/**
 * TypeScript-side mirrors of the CSS design tokens.
 *
 * The source of truth is `app/globals.css` (declared via @theme so Tailwind
 * v4 picks them up). These constants exist for places where we need the
 * literal value at runtime — animation timing functions, motion durations,
 * status colour lookups, etc.
 *
 * Rules:
 *   - Never hard-code colours in components. Reference `STATUS_COLORS`
 *     or use Tailwind classes that consume the tokens.
 *   - Motion uses durations defined here; don't sprinkle ad hoc ms values.
 */

export const MOTION = {
  fast: 0.12,
  default: 0.22,
  slow: 0.42,
} as const;

export const EASE = {
  cinematicOut: [0.2, 0.8, 0.2, 1] as [number, number, number, number],
  cinematicInOut: [0.7, 0, 0.2, 1] as [number, number, number, number],
} as const;

export const STATUS_COLORS = {
  queued: "var(--color-status-queued)",
  running: "var(--color-status-running)",
  succeeded: "var(--color-status-succeeded)",
  failed: "var(--color-status-failed)",
  warning: "var(--color-status-warning)",
  fresh: "var(--color-status-fresh)",
  maturing: "var(--color-status-maturing)",
  stable: "var(--color-status-stable)",
  decayed: "var(--color-status-decayed)",
} as const;

export const SURFACE_CLASSES = {
  /** Page background container */
  page: "bg-[color:var(--color-surface-0)] text-[color:var(--color-text-primary)]",
  /** Sidebar / non-elevated card */
  panel: "bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)]",
  /** Standard card */
  card: "bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] rounded-2xl",
  /** Elevated / important card */
  elevated: "bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-strong)] rounded-2xl",
  /** Glass overlay for modals / sticky bars */
  glass: "bg-[color:var(--color-surface-glass)] backdrop-blur-xl border border-[color:var(--color-border-soft)] rounded-2xl",
} as const;

export type StatusKey = keyof typeof STATUS_COLORS;
