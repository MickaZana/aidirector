/**
 * Development environment configuration.
 *
 * These values are optimised for local development — relaxed limits,
 * verbose logging, short timeouts for fast feedback.
 */
import type { AppConfig } from "./index";

const development: AppConfig = {
  env: "development",

  // ── Upload ──────────────────────────────────────────────────────────
  upload: {
    maxFileSizeBytes: 500 * 1024 * 1024, // 500 MB
    maxQueueEntries: 12,
    allowedMimeTypes: ["video/mp4", "video/quicktime", "video/x-msvideo"],
    presignTimeoutMs: 10_000,
    uploadTimeoutMs: 300_000, // 5 min
  },

  // ── Processing ──────────────────────────────────────────────────────
  processing: {
    maxClipsPerJob: 12,
    maxRetries: 3,
    pollingIntervalMs: 4_000, // 4 seconds
    webSocketReconnectMs: 3_000,
  },

  // ── Notifications ───────────────────────────────────────────────────
  notifications: {
    defaultDurationMs: {
      success: 4_000,
      error: 8_000,
      warning: 6_000,
      info: 4_000,
    },
  },

  // ── Storage ─────────────────────────────────────────────────────────
  storage: {
    provider: "local",
    maxLocalStorageBytes: 5 * 1024 * 1024, // 5 MB (localStorage limit)
  },

  // ── API ─────────────────────────────────────────────────────────────
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    requestTimeoutMs: 15_000,
    retryCount: 1,
  },
};

export default development;
