/**
 * Testing environment configuration.
 *
 * Minimal, deterministic values for unit and integration tests.
 * Overrides are applied via environment variables in CI.
 */
import type { AppConfig } from "./index";

const testing: AppConfig = {
  env: "testing",

  upload: {
    maxFileSizeBytes: 100 * 1024 * 1024, // 100 MB (smaller for fast tests)
    maxQueueEntries: 5,
    allowedMimeTypes: ["video/mp4", "video/quicktime"],
    presignTimeoutMs: 5_000,
    uploadTimeoutMs: 60_000,
  },

  processing: {
    maxClipsPerJob: 6,
    maxRetries: 1,
    pollingIntervalMs: 500, // fast for tests
    webSocketReconnectMs: 1_000,
  },

  notifications: {
    defaultDurationMs: {
      success: 100,  // essentially instant for tests
      error: 100,
      warning: 100,
      info: 100,
    },
  },

  storage: {
    provider: "local",
    maxLocalStorageBytes: 1 * 1024 * 1024,
  },

  api: {
    baseUrl: "http://localhost:8000",
    requestTimeoutMs: 5_000,
    retryCount: 0,
  },
};

export default testing;
