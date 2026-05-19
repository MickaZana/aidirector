import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Use a child element as the trigger (e.g. wrap an <a>). */
  asChild?: boolean;
}

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-5 text-sm",
};

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-gradient-to-b from-[color:var(--color-accent-green)] to-[color:var(--color-accent-green-dim)] text-[color:var(--color-text-inverse)] font-semibold shadow-[0_1px_0_rgba(255,255,255,0.25)_inset,0_8px_24px_-8px_rgba(0,230,161,0.6)] hover:saturate-125 active:translate-y-[1px]",
  secondary:
    "bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-strong)] text-[color:var(--color-text-primary)] hover:border-[color:var(--color-border-accent)] hover:bg-[color:var(--color-surface-3)]",
  ghost:
    "bg-transparent text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)] hover:bg-[color:var(--color-surface-1)]",
  danger:
    "bg-[color:var(--color-accent-magenta)]/15 text-[color:var(--color-accent-magenta)] border border-[color:var(--color-accent-magenta)]/40 hover:bg-[color:var(--color-accent-magenta)]/25",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", asChild, className, ...rest }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref as React.Ref<HTMLButtonElement>}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg font-medium tracking-tight transition-all duration-[var(--motion-fast)] ease-[cubic-bezier(0.2,0.8,0.2,1)] disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap",
          SIZE_CLASSES[size],
          VARIANT_CLASSES[variant],
          className,
        )}
        {...rest}
      />
    );
  },
);
Button.displayName = "Button";
