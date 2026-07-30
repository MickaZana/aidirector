/**
 * Notifications — barrel exports.
 *
 * Usage:
 *   import { ToastNotificationProvider } from "@/services/notifications";
 *   // or through the service registry:
 *   import { Services } from "@/services";
 *   Services.notifications.success("Upload complete");
 */

export type { NotificationProvider, NotificationVariant, NotificationOptions } from "./Provider";
export { ToastNotificationProvider } from "./ToastNotificationProvider";
