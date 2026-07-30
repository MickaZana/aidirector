/**
 * Box shadow values for the design system.
 * Subtle shadows — no heavy shadows per spec.
 */
export const shadows = {
  /** Card default shadow */
  card: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
  /** Card hover shadow */
  cardHover: "0 4px 12px 0 rgba(0, 0, 0, 0.06)",
  /** Elevated element shadow */
  elevated: "0 8px 24px 0 rgba(0, 0, 0, 0.08)",
  /** Modal / dialog shadow */
  modal: "0 20px 60px 0 rgba(0, 0, 0, 0.12)",
} as const;

export type ShadowKey = keyof typeof shadows;
