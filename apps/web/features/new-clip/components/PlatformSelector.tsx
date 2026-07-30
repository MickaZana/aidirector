"use client";

import { AppIcon } from "@/features/design-system";
import { cn } from "@/features/design-system/utils/cn";

interface Platform {
  id: string;
  label: string;
}

interface PlatformSelectorProps {
  platforms: Platform[];
  selected: string[];
  onChange: (ids: string[]) => void;
}

/**
 * Platform selector — checkbox-style cards, multiple selection.
 * Platforms passed as props (sourced from constants/platforms.ts at call site).
 * Ask: "Where do you want to publish?"
 */
export function PlatformSelector({
  platforms,
  selected,
  onChange,
}: PlatformSelectorProps) {
  const toggle = (id: string) => {
    if (selected.includes(id)) {
      onChange(selected.filter((s) => s !== id));
    } else {
      onChange([...selected, id]);
    }
  };

  return (
    <section>
      <h2 className="text-lg font-semibold text-slate-900">
        Where do you want to publish?
      </h2>
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
        {platforms.map((p) => {
          const active = selected.includes(p.id);
          return (
            <button
              key={p.id}
              type="button"
              role="checkbox"
              aria-checked={active}
              onClick={() => toggle(p.id)}
              className={cn(
                "flex items-center gap-4 rounded-2xl border-2 px-5 py-4 transition-all duration-200 text-left",
                active
                  ? "border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500/20"
                  : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm",
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-6 shrink-0 items-center justify-center rounded-md border-2 transition-colors",
                  active
                    ? "border-emerald-500 bg-emerald-500 text-white"
                    : "border-slate-300 bg-white",
                )}
              >
                {active && <AppIcon name="check" size="sm" strokeWidth={3} />}
              </span>
              <span
                className={cn(
                  "text-base font-medium",
                  active ? "text-slate-900" : "text-slate-700",
                )}
              >
                {p.label}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
