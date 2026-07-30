/**
 * Production environment configuration.
 *
 * Stricter limits, longer timeouts (real uploads are large), and safe
 * defaults for a live SaaS application.
 */
import type { AppConfig } from "./index";

const production: AppConfig = {
  env: "production",

  upload: {
    maxFileSizeBytes: 3 * 1024 * 1024 * 1024, // 3 GB
    maxQueueEntries: 12,
    allowedMimeTypes: [
      "video/mp4",
      "video/quicktime",
      "video/x-msvideo",
      "video/x-matroska",
      "video/webm",
    ],
    presignTimeoutMs: 15_000,
    uploadTimeoutMs: 600_000, // 10 min
  },

  processing: {
    maxClipsPerJob: 12,
    maxRetries: 3,
    pollingIntervalMs: 4_000,
    webSocketReconnectMs: 3_000,
  },

  notifications: {
    defaultDurationMs: {
      success: 4_000,
      error: 8_000,
      warning: 6_000,
      info: 4_000,
    },
  },

  storage: {
    provider: "r2",
    maxLocalStorageBytes: 0, // not used in production
  },

  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "https://api.aidirector.app",
    requestTimeoutMs: 30_000,
    retryCount: 2,
  },
};

export default production;
