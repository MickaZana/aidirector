"use client";

import { AppIcon } from "@/features/design-system";
import { cn } from "@/features/design-system/utils/cn";

interface ClipCountSelectorProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
}

/**
 * Stepper for selecting clip count.
 * Range 6–24, default 12.
 * Ask: "How many clips would you like?"
 */
export function ClipCountSelector({
  value,
  onChange,
  min = 6,
  max = 24,
}: ClipCountSelectorProps) {
  const decrement = () => {
    if (value > min) onChange(value - 1);
  };

  const increment = () => {
    if (value < max) onChange(value + 1);
  };

  return (
    <section>
      <h2 className="text-lg font-semibold text-slate-900">
        How many clips would you like?
      </h2>
      <div className="mt-4 flex items-center justify-center gap-6">
        <button
          type="button"
          onClick={decrement}
          disabled={value <= min}
          aria-label="Decrease clip count"
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-xl border-2 transition-all duration-200",
            value <= min
              ? "border-slate-100 bg-slate-50 text-slate-300 cursor-not-allowed"
              : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300 hover:text-emerald-600 hover:shadow-sm",
          )}
        >
          <AppIcon name="minus" size="md" strokeWidth={2} />
        </button>

        <div className="flex flex-col items-center">
          <span
            className="text-4xl font-bold text-slate-900 tabular-nums"
            aria-live="polite"
            aria-atomic="true"
          >
            {value}
          </span>
          <span className="text-sm text-slate-400 mt-0.5">clips</span>
        </div>

        <button
          type="button"
          onClick={increment}
          disabled={value >= max}
          aria-label="Increase clip count"
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-xl border-2 transition-all duration-200",
            value >= max
              ? "border-slate-100 bg-slate-50 text-slate-300 cursor-not-allowed"
              : "border-slate-200 bg-white text-slate-600 hover:border-emerald-300 hover:text-emerald-600 hover:shadow-sm",
          )}
        >
          <AppIcon name="plus" size="md" strokeWidth={2} />
        </button>
      </div>
    </section>
  );
}
