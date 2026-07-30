/**
 * Animation durations and easings for the design system.
 * Maximum 250ms per spec. No bounce easings.
 */
export const animations = {
  /** Fast — hover states, micro-interactions (150ms) */
  fast: "150ms",
  /** Default — transitions, color changes (200ms) */
  default: "200ms",
  /** Slow — layout animations, enter/exit (250ms) */
  slow: "250ms",
} as const;

export const easings = {
  /** Standard ease out */
  easeOut: [0.2, 0.8, 0.2, 1] as [number, number, number, number],
  /** Standard ease in-out */
  easeInOut: [0.4, 0, 0.2, 1] as [number, number, number, number],
} as const;

export type AnimationKey = keyof typeof animations;
