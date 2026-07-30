/**
 * Toast notification store.
 *
 * Lightweight zustand store for transient UI notifications — success,
 * error, warning, info. Toasts auto-dismiss after a configurable duration.
 * The Toaster component renders them from this store.
 *
 * Duration defaults come from the application config layer. Override per
 * toast by passing an explicit `durationMs`.
 */
import { create } from "zustand";
import { config } from "@/config";

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  message?: string;
  durationMs: number;
  /** Optional action button. */
  action?: { label: string; onClick: () => void };
}

interface ToastState {
  toasts: Toast[];
  add: (toast: Omit<Toast, "id" | "durationMs"> & { durationMs?: number }) => string;
  remove: (id: string) => void;
  clear: () => void;
}

let toastCounter = 0;
const localId = () => `toast_${Date.now()}_${++toastCounter}`;

const DEFAULT_DURATION = config.notifications.defaultDurationMs;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  add(toast) {
    const id = localId();
    const durationMs = toast.durationMs ?? DEFAULT_DURATION[toast.variant];
    set((s) => ({
      toasts: [...s.toasts, { ...toast, id, durationMs }],
    }));
    return id;
  },
  remove(id) {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  },
  clear() {
    set({ toasts: [] });
  },
}));

/** Convenience helpers — call these from components/hooks. */
export const toast = {
  success: (title: string, message?: string) =>
    useToastStore.getState().add({ variant: "success", title, message }),
  error: (title: string, message?: string) =>
    useToastStore.getState().add({ variant: "error", title, message }),
  warning: (title: string, message?: string) =>
    useToastStore.getState().add({ variant: "warning", title, message }),
  info: (title: string, message?: string) =>
    useToastStore.getState().add({ variant: "info", title, message }),
};
