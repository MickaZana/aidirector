"use client";

import { useEffect, useState } from "react";
import { cn } from "../utils/cn";
import { AppIcon } from "../components/AppIcon";

interface ErrorToastProps {
  message: string;
  /** Auto-dismiss duration in ms (default: 6000). Set to 0 to disable auto-dismiss. */
  duration?: number;
  /** Controlled visibility */
  visible: boolean;
  /** Called when toast should be dismissed */
  onDismiss?: () => void;
  className?: string;
}

/**
 * ErrorToast — A red error toast with auto-dismiss.
 *
 * Usage:
 *   const [show, setShow] = useState(false);
 *   <ErrorToast
 *     message="Something went wrong. Please try again."
 *     visible={show}
 *     onDismiss={() => setShow(false)}
 *   />
 *
 * Accessible: uses `role="alert"` and `aria-live="assertive"`.
 */
export function ErrorToast({
  message,
  duration = 6000,
  visible,
  onDismiss,
  className,
}: ErrorToastProps) {
  const [mounted, setMounted] = useState(false);
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    if (visible) {
      setMounted(true);
      requestAnimationFrame(() => setAnimating(true));

      if (duration > 0 && onDismiss) {
        const timer = setTimeout(() => {
          setAnimating(false);
          setTimeout(() => {
            setMounted(false);
            onDismiss();
          }, 200);
        }, duration);
        return () => clearTimeout(timer);
      }
    } else {
      setAnimating(false);
      const timer = setTimeout(() => setMounted(false), 200);
      return () => clearTimeout(timer);
    }
  }, [visible, duration, onDismiss]);

  if (!mounted) return null;

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={cn(
        "fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 px-5 py-4 shadow-lg transition-all duration-200",
        animating
          ? "translate-y-0 opacity-100"
          : "translate-y-4 opacity-0",
        className,
      )}
    >
      <AppIcon
        name="alertCircle"
        size="md"
        className="text-red-500 shrink-0"
      />
      <p className="text-sm font-medium text-red-900">{message}</p>
      {onDismiss && (
        <button
          onClick={() => {
            setAnimating(false);
            setTimeout(() => {
              setMounted(false);
              onDismiss();
            }, 200);
          }}
          className="ml-2 shrink-0 rounded-lg p-1 text-red-600 hover:bg-red-100 transition-colors"
          aria-label="Dismiss"
        >
          <AppIcon name="x" size="sm" />
        </button>
      )}
    </div>
  );
}
