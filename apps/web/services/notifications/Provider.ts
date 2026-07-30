/**
 * Notification Provider interface.
 *
 * Abstracts all user-facing notifications — toasts, banners, dialogs —
 * behind a single contract. Components should never call toast stores,
 * toast libraries, or DOM APIs directly.
 *
 * Implementations:
 *   - ToastNotificationProvider  (current: wraps zustand toast-store)
 *   - InAppNotificationProvider  (future: notification center / bell icon)
 *   - PushNotificationProvider   (future: browser Push API)
 */

export type NotificationVariant =
  | "success"
  | "error"
  | "warning"
  | "info";

export interface NotificationOptions {
  /** Duration in milliseconds before auto-dismiss. 0 = persistent. */
  durationMs?: number;
  /** Optional action button. */
  action?: { label: string; onClick: () => void };
}

export interface NotificationProvider {
  /**
   * Show a success notification.
   * @param title   - Brief headline
   * @param message - Optional detail body
   * @param options - Optional configuration
   * @returns A notification ID that can be used to dismiss it
   */
  success(title: string, message?: string, options?: NotificationOptions): string;

  /**
   * Show an error notification.
   * @param title   - Brief headline
   * @param message - Optional detail body
   * @param options - Optional configuration
   * @returns A notification ID that can be used to dismiss it
   */
  error(title: string, message?: string, options?: NotificationOptions): string;

  /**
   * Show a warning notification.
   * @param title   - Brief headline
   * @param message - Optional detail body
   * @param options - Optional configuration
   * @returns A notification ID that can be used to dismiss it
   */
  warning(title: string, message?: string, options?: NotificationOptions): string;

  /**
   * Show an informational notification.
   * @param title   - Brief headline
   * @param message - Optional detail body
   * @param options - Optional configuration
   * @returns A notification ID that can be used to dismiss it
   */
  info(title: string, message?: string, options?: NotificationOptions): string;

  /**
   * Dismiss a notification by ID.
   * @param id - The notification ID returned by one of the show methods
   */
  dismiss(id: string): void;

  /**
   * Dismiss all active notifications.
   */
  dismissAll(): void;
}
