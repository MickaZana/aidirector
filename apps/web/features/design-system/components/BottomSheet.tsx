"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { cn } from "../utils/cn";
import { AppIcon } from "./AppIcon";

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
  className?: string;
}

/**
 * BottomSheet — A mobile-friendly panel that slides up from the bottom.
 * On desktop it behaves like a right-side drawer.
 *
 * Usage:
 *   <BottomSheet open={!!selectedClip} onClose={() => setSelectedClip(null)} title="Clip Preview">
 *     ...content...
 *   </BottomSheet>
 *
 * Accessible: focus trap, Escape to close, backdrop click to close,
 * `role="dialog"` with `aria-modal="true"`.
 */
export function BottomSheet({
  open,
  onClose,
  title,
  children,
  className,
}: BottomSheetProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Focus trap + Escape key
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }

      // Trap Tab within the panel
      if (e.key === "Tab" && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm md:bg-black/20 md:backdrop-blur-0"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel: bottom sheet on mobile, right drawer on md+ */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ?? "Panel"}
        className={cn(
          // Mobile: fixed bottom sheet
          "fixed bottom-0 left-0 right-0 z-50",
          "rounded-t-2xl bg-white border border-slate-200 shadow-xl",
          "max-h-[85vh] overflow-y-auto",
          "transition-transform duration-300 motion-safe:transition-transform motion-safe:duration-300",
          // Desktop: right-side drawer
          "md:rounded-none md:fixed md:top-0 md:right-0 md:left-auto md:bottom-0",
          "md:w-[480px] md:max-h-none md:shadow-2xl",
          "md:border-r-0 md:border-t-0 md:border-b-0",
          className,
        )}
      >
        {/* Handle bar (mobile visual indicator) */}
        <div className="md:hidden flex justify-center pt-2 pb-1">
          <div className="h-1 w-10 rounded-full bg-slate-300" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
          <h2 className="text-base font-semibold text-slate-900">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
            aria-label="Close panel"
          >
            <AppIcon name="x" size="md" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5">{children}</div>
      </div>
    </>
  );
}
