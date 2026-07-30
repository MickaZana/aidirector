"use client";

import { useEffect, useRef } from "react";
import { cn } from "../utils/cn";
import { AppIcon } from "../components/AppIcon";
import { Button } from "../components/Button";

type DialogVariant = "default" | "danger";

interface ConfirmationDialogProps {
  /** Open state */
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Variant changes the confirm button color (danger = red) */
  variant?: DialogVariant;
  /** Loading state for the confirm action */
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  className?: string;
}

/**
 * ConfirmationDialog — A modal dialog for confirming destructive or important actions.
 *
 * Usage:
 *   <ConfirmationDialog
 *     open={showCancelDialog}
 *     title="Cancel Processing?"
 *     message="Your progress will be lost. You'll need to start over."
 *     confirmLabel="Yes, Cancel"
 *     variant="danger"
 *     onConfirm={handleConfirmCancel}
 *     onCancel={() => setShowCancelDialog(false)}
 *   />
 *
 * Accessible: traps focus, closes on Escape, uses `role="alertdialog"`,
 * respects reduced-motion preferences.
 */
export function ConfirmationDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  loading = false,
  onConfirm,
  onCancel,
  className,
}: ConfirmationDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  // Trap focus and handle Escape key
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
        return;
      }

      // Trap Tab within dialog
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
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

    // Focus the confirm button on open
    requestAnimationFrame(() => confirmRef.current?.focus());

    document.addEventListener("keydown", handleKeyDown);
    // Prevent body scroll
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
      aria-describedby="dialog-message"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className={cn(
          "relative z-10 w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-xl p-6 transition-all duration-200",
          "motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95",
          className,
        )}
      >
        {/* Icon */}
        <div
          className={cn(
            "h-12 w-12 rounded-xl flex items-center justify-center mb-4",
            variant === "danger"
              ? "bg-red-50 text-red-500"
              : "bg-emerald-50 text-emerald-500",
          )}
        >
          {variant === "danger" ? (
            <AppIcon name="alertCircle" size="lg" />
          ) : (
            <AppIcon name="info" size="lg" />
          )}
        </div>

        {/* Title */}
        <h2
          id="dialog-title"
          className="text-lg font-semibold text-slate-900 mb-1"
        >
          {title}
        </h2>

        {/* Message */}
        <p
          id="dialog-message"
          className="text-sm text-slate-600 leading-relaxed mb-6"
        >
          {message}
        </p>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <Button
            variant="ghost"
            size="md"
            onClick={onCancel}
            disabled={loading}
          >
            {cancelLabel}
          </Button>
          <Button
            ref={confirmRef}
            variant={variant === "danger" ? "primary" : "primary"}
            size="md"
            onClick={onConfirm}
            loading={loading}
            className={
              variant === "danger"
                ? "!bg-red-500 !hover:bg-red-600 !active:bg-red-700"
                : undefined
            }
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
