import type { colors } from "../constants/colors";
import type { spacing } from "../constants/spacing";
import type { radius } from "../constants/radius";

/** Polymorphic component as-prop — allows rendering as any HTML element */
export type AsProp<T extends React.ElementType = "div"> = {
  as?: T;
};

/** Responsive value — single value or breakpoint-specific object */
export type ResponsiveValue<T> = T | { sm?: T; md?: T; lg?: T };

/** Common spacing props shared across layout components */
export interface SpacingProps {
  /** Padding (4px base unit) */
  p?: keyof typeof spacing;
  /** Horizontal padding */
  px?: keyof typeof spacing;
  /** Vertical padding */
  py?: keyof typeof spacing;
  /** Margin bottom */
  mb?: keyof typeof spacing;
  /** Gap between children */
  gap?: keyof typeof spacing;
}

/** Common border radius prop */
export interface RadiusProp {
  radius?: keyof typeof radius;
}

/** Status tones */
export type StatusTone = "success" | "warning" | "error" | "info" | "neutral";

/** Component size */
export type ComponentSize = "sm" | "md" | "lg";
