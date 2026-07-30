"use client";

import type { ElementType } from "react";
import { cn } from "../utils/cn";

interface IconButtonProps {
  icon: ElementType;
  /** Accessible label (always required for icon-only buttons) */
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
  variant?: "default" | "ghost" | "primary";
}

const SIZE_CLASSES = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-12 w-12",
};

const ICON_SIZES = {
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
};

const VARIANT_CLASSES = {
  default:
    "bg-white border border-slate-200 text-slate-500 hover:bg-slate-50 hover:border-slate-300",
  ghost: "bg-transparent text-slate-400 hover:text-slate-600 hover:bg-slate-100",
  primary:
    "bg-emerald-500 text-white hover:bg-emerald-600 active:bg-emerald-700",
};

/**
 * IconButton — circular icon-only button.
 * Always requires an accessible label.
 */
export function IconButton({
  icon: Icon,
  label,
  onClick,
  disabled = false,
  className,
  size = "md",
  variant = "default",
}: IconButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      className={cn(
        "inline-flex items-center justify-center rounded-full transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed",
        SIZE_CLASSES[size],
        VARIANT_CLASSES[variant],
        className,
      )}
    >
      <Icon className={ICON_SIZES[size]} strokeWidth={2} />
    </button>
  );
}
