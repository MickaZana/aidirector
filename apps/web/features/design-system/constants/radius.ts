/**
 * Border radius values for the design system.
 * Following the spec: 16px radius for cards.
 */
export const radius = {
  /** Small — buttons, inputs (8px) */
  sm: "8px",
  /** Medium — cards, sections (12px) */
  md: "12px",
  /** Large — cards, dialogs (16px) */
  lg: "16px",
  /** Extra large — modals (20px) */
  xl: "20px",
  /** Full — pills, badges (9999px) */
  full: "9999px",
} as const;

export type RadiusKey = keyof typeof radius;
