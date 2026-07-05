"use client";

/**
 * Toast notification renderer.
 *
 * Renders the toast stack from `useToastStore` in a fixed overlay at the
 * top-right of the viewport. Auto-dismisses each toast after its duration.
 * Place once in the root layout.
 */
import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useToastStore, type ToastVariant } from "@/stores/toast-store";
import { cn } from "@/lib/cn";

const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 className="h-4 w-4 text-[color:var(--color-status-succeeded)]" />,
  error: <XCircle className="h-4 w-4 text-[color:var(--color-status-failed)]" />,
  warning: <AlertCircle className="h-4 w-4 text-[color:var(--color-status-warning)]" />,
  info: <Info className="h-4 w-4 text-[color:var(--color-status-running)]" />,
};

const BORDERS: Record<ToastVariant, string> = {
  success: "border-l-[color:var(--color-status-succeeded)]",
  error: "border-l-[color:var(--color-status-failed)]",
  warning: "border-l-[color:var(--color-status-warning)]",
  info: "border-l-[color:var(--color-status-running)]",
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const remove = useToastStore((s) => s.remove);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Manage auto-dismiss timers
  useEffect(() => {
    for (const t of toasts) {
      if (!timers.current.has(t.id)) {
        timers.current.set(
          t.id,
          setTimeout(() => remove(t.id), t.durationMs),
        );
      }
    }
    // Clean up timers for removed toasts
    for (const [id] of timers.current) {
      if (!toasts.some((t) => t.id === id)) {
        clearTimeout(timers.current.get(id));
        timers.current.delete(id);
      }
    }
  }, [toasts, remove]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      for (const timer of timers.current.values()) clearTimeout(timer);
    };
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, x: 80, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 80, scale: 0.95 }}
            transition={{ duration: 0.2, ease: [0.2, 0.8, 0.2, 1] }}
            className={cn(
              "pointer-events-auto rounded-lg border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-2)] shadow-[var(--shadow-elevated)] border-l-4 overflow-hidden",
              BORDERS[t.variant],
            )}
          >
            <div className="flex items-start gap-3 p-4">
              <div className="mt-0.5 shrink-0">{ICONS[t.variant]}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold tracking-tight text-[color:var(--color-text-primary)]">
                  {t.title}
                </p>
                {t.message && (
                  <p className="mt-0.5 text-xs text-[color:var(--color-text-secondary)] leading-relaxed">
                    {t.message}
                  </p>
                )}
                {t.action && (
                  <button
                    onClick={t.action.onClick}
                    className="mt-2 text-xs font-semibold text-[color:var(--color-accent-green)] hover:text-[color:var(--color-accent-green-dim)] transition-colors"
                  >
                    {t.action.label}
                  </button>
                )}
              </div>
              <button
                onClick={() => remove(t.id)}
                className="shrink-0 h-5 w-5 rounded-full flex items-center justify-center text-[color:var(--color-text-tertiary)] hover:text-[color:var(--color-text-primary)] hover:bg-[color:var(--color-surface-3)] transition-colors"
              >
                <X className="h-3 w-3" strokeWidth={2} />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
