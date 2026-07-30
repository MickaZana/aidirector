/**
 * Service Registry — central dependency resolution.
 *
 * Every provider-based service in the application is accessible through
 * this object. Components never import concrete implementations directly;
 * they import `Services` and let the registry decide which provider to
 * return based on the current environment/configuration.
 *
 * Usage:
 *   import { Services } from "@/services";
 *   Services.notifications.success("Upload complete");
 *   Services.analytics.track("page_view", { page: "/app" });
 *
 * To swap a provider (e.g., local storage → R2):
 *   1. Implement the provider interface
 *   2. Swap it here
 *   3. All consumers pick up the new implementation automatically
 */

import { config } from "@/config";
import { analytics } from "@/services/analytics";
import { ToastNotificationProvider } from "@/services/notifications";
import { LocalStorageProvider } from "@/services/storage";
import { LocalQueue } from "@/services/processingQueue";
import type { Analytics } from "@/services/analytics";
import type { NotificationProvider } from "@/services/notifications";
import type { StorageProvider } from "@/services/storage";
import type { QueueProvider } from "@/services/processingQueue";

// ─── Instances (singletons) ────────────────────────────────────────────

const notificationProvider: NotificationProvider = new ToastNotificationProvider();
const storageProvider: StorageProvider = new LocalStorageProvider();
const queueProvider: QueueProvider = new LocalQueue();

// ─── Exported registry ─────────────────────────────────────────────────

export const Services = {
  /** User-facing notifications (toasts, banners, etc.) */
  get notifications(): NotificationProvider {
    return notificationProvider;
  },

  /** File storage abstraction */
  get storage(): StorageProvider {
    return storageProvider;
  },

  /** Processing queue abstraction */
  get queue(): QueueProvider {
    return queueProvider;
  },

  /** Product analytics */
  get analytics(): Analytics {
    return analytics;
  },

  /** Application configuration */
  get config(): typeof config {
    return config;
  },
} as const;

export type ServiceRegistry = typeof Services;
