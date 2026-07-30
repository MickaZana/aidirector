/**
 * Typography scale for creator screens.
 * Font sizes, weights, line heights, and letter spacing.
 *
 * Font family: Inter (set at app level in globals.css)
 */
export const typography = {
  /** Hero title — 48px Bold */
  hero: {
    size: "48px",
    weight: "700",
    lineHeight: "1.1",
    letterSpacing: "-0.02em",
  },
  /** Section title — 30px Bold */
  sectionTitle: {
    size: "30px",
    weight: "700",
    lineHeight: "1.2",
    letterSpacing: "-0.01em",
  },
  /** Page / card title — 24px Semibold */
  title: {
    size: "24px",
    weight: "600",
    lineHeight: "1.25",
    letterSpacing: "-0.01em",
  },
  /** Subtitle — 18px Regular */
  subtitle: {
    size: "18px",
    weight: "400",
    lineHeight: "1.5",
    letterSpacing: "0",
  },
  /** Body text — 16px Regular */
  body: {
    size: "16px",
    weight: "400",
    lineHeight: "1.5",
    letterSpacing: "0",
  },
  /** Small text — 14px Regular */
  small: {
    size: "14px",
    weight: "400",
    lineHeight: "1.4",
    letterSpacing: "0",
  },
  /** Caption / metadata — 12px Regular */
  caption: {
    size: "12px",
    weight: "400",
    lineHeight: "1.3",
    letterSpacing: "0",
  },
  /** Button label — 18px Medium */
  button: {
    size: "18px",
    weight: "500",
    lineHeight: "1",
    letterSpacing: "0",
  },
  /** Overline / label — 11px Uppercase */
  overline: {
    size: "11px",
    weight: "600",
    lineHeight: "1.2",
    letterSpacing: "0.08em",
  },
} as const;

export type TypographyKey = keyof typeof typography;
