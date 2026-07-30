"use client";

import type { ReactNode, ElementType } from "react";
import { cn } from "../utils/cn";

type TypographyVariant =
  | "hero"
  | "sectionTitle"
  | "title"
  | "subtitle"
  | "body"
  | "small"
  | "caption"
  | "overline";

interface TypographyProps {
  variant?: TypographyVariant;
  children: ReactNode;
  className?: string;
  as?: ElementType;
  /** Accessible id for heading anchors */
  id?: string;
}

const VARIANT_TAGS: Record<TypographyVariant, ElementType> = {
  hero: "h1",
  sectionTitle: "h2",
  title: "h3",
  subtitle: "h2",
  body: "p",
  small: "p",
  caption: "span",
  overline: "span",
};

const VARIANT_CLASSES: Record<TypographyVariant, string> = {
  hero: "text-[48px] font-bold leading-[1.1] tracking-tight text-slate-900",
  sectionTitle:
    "text-[30px] font-bold leading-[1.2] tracking-tight text-slate-900",
  title: "text-2xl font-semibold leading-[1.25] tracking-tight text-slate-900",
  subtitle: "text-lg leading-[1.5] text-slate-500",
  body: "text-base leading-[1.5] text-slate-700",
  small: "text-sm leading-[1.4] text-slate-500",
  caption: "text-xs leading-[1.3] text-slate-400",
  overline:
    "text-[11px] font-semibold leading-[1.2] tracking-[0.08em] uppercase text-slate-400",
};

/**
 * Typography component — renders semantic HTML tags with consistent styling.
 *
 * Examples:
 *   <Typography variant="hero">Title</Typography>       → <h1>
 *   <Typography variant="subtitle">Subtitle</Typography> → <h2>
 *   <Typography variant="body">Body text</Typography>    → <p>
 */
export function Typography({
  variant = "body",
  children,
  className,
  as,
  id,
}: TypographyProps) {
  const Component = as ?? VARIANT_TAGS[variant];

  return (
    <Component id={id} className={cn(VARIANT_CLASSES[variant], className)}>
      {children}
    </Component>
  );
}
