/**
 * Light theme color palette for the creator screens.
 * Source of truth for all colors used in the design system.
 *
 * When adding dark theme support, duplicate this file as colors-dark.ts
 * and swap via context/provider.
 */
export const colors = {
  /** Page background */
  background: "#F8FAFC",
  /** Card / surface backgrounds */
  surface: "#FFFFFF",
  /** Primary text */
  textPrimary: "#0F172A",
  /** Secondary / muted text */
  textSecondary: "#64748B",
  /** Tertiary / placeholder text */
  textTertiary: "#94A3B8",
  /** Accent / brand color */
  accent: "#10B981",
  /** Accent hover state */
  accentHover: "#059669",
  /** Accent active state */
  accentActive: "#047857",
  /** Accent light backgrounds */
  accentLight: "#ECFDF5",
  /** Accent light border */
  accentBorder: "#A7F3D0",
  /** Default border */
  border: "#E2E8F0",
  /** Hover border */
  borderHover: "#CBD5E1",
  /** Subtle background (hover states) */
  surfaceHover: "#F1F5F9",
  /** White */
  white: "#FFFFFF",
  /** Black (rarely used) */
  black: "#000000",
  /** Error */
  error: "#EF4444",
  /** Error light */
  errorLight: "#FEF2F2",
  /** Warning */
  warning: "#F59E0B",
  /** Warning light */
  warningLight: "#FFFBEB",
  /** Success / positive */
  success: "#10B981",
  /** Success light */
  successLight: "#ECFDF5",
} as const;

export type ColorKey = keyof typeof colors;
