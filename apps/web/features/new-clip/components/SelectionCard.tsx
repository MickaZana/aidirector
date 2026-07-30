"use client";

import { cn } from "@/features/design-system/utils/cn";
import type { ReactNode } from "react";

interface SelectionCardProps {
  selected?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  /** Accessible label for the card when used as a radio/checkbox */
  ariaLabel?: string;
}

/**
 * Reusable selection card used for video type, platform, and option cards.
 * Behaves as a styled button with selected/disabled states.
 * Rounded-2xl (16px) per spec, white bg, emerald accent when selected.
 */
export function SelectionCard({
  selected = false,
  disabled = false,
  onClick,
  children,
  className,
  ariaLabel,
}: SelectionCardProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-pressed={selected}
      aria-label={ariaLabel}
      className={cn(
        "relative w-full rounded-2xl border-2 px-5 py-5 text-left transition-all duration-200",
        selected
          ? "border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500/20"
          : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm",
        disabled && "cursor-not-allowed opacity-50",
        className,
      )}
    >
      {children}
    </button>
  );
}
