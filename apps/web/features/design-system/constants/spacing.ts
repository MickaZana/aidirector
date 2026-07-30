/**
 * Spacing scale — consistent gap, margin, and padding values.
 * Follows a 4px base unit (matching Tailwind defaults).
 *
 * Use these values directly or via the Stack component's gap prop.
 */
export const spacing = {
  /** 0px */
  0: "0px",
  /** 4px */
  1: "0.25rem",
  /** 8px */
  2: "0.5rem",
  /** 12px */
  3: "0.75rem",
  /** 16px */
  4: "1rem",
  /** 20px */
  5: "1.25rem",
  /** 24px */
  6: "1.5rem",
  /** 28px */
  7: "1.75rem",
  /** 32px */
  8: "2rem",
  /** 40px */
  10: "2.5rem",
  /** 48px */
  12: "3rem",
  /** 64px */
  16: "4rem",
  /** 80px */
  20: "5rem",
} as const;

export type SpacingKey = keyof typeof spacing;
