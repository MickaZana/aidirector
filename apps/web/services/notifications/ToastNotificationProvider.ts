/**
 * ToastNotificationProvider — wraps the zustand toast-store behind the
 * NotificationProvider interface.
 *
 * This is the default notification provider for the current app. It uses
 * the existing Toaster component to render toasts. To swap to a different
 * UI (e.g., an in-app notification center), implement NotificationProvider
 * and swap it in the service registry.
 */

import type { NotificationProvider, NotificationOptions } from "./Provider";
import { useToastStore } from "@/stores/toast-store";

export class ToastNotificationProvider implements NotificationProvider {
  private get store() {
    return useToastStore.getState();
  }

  success(title: string, message?: string, options?: NotificationOptions): string {
    return this.store.add({
      variant: "success",
      title,
      message,
      durationMs: options?.durationMs,
      action: options?.action,
    });
  }

  error(title: string, message?: string, options?: NotificationOptions): string {
    return this.store.add({
      variant: "error",
      title,
      message,
      durationMs: options?.durationMs,
      action: options?.action,
    });
  }

  warning(title: string, message?: string, options?: NotificationOptions): string {
    return this.store.add({
      variant: "warning",
      title,
      message,
      durationMs: options?.durationMs,
      action: options?.action,
    });
  }

  info(title: string, message?: string, options?: NotificationOptions): string {
    return this.store.add({
      variant: "info",
      title,
      message,
      durationMs: options?.durationMs,
      action: options?.action,
    });
  }

  dismiss(id: string): void {
    this.store.remove(id);
  }

  dismissAll(): void {
    this.store.clear();
  }
}
