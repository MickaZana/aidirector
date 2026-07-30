/**
 * Application configuration layer.
 *
 * All magic numbers, limits, timeouts, and environment-specific values
 * live here. No file in the application should contain hardcoded
 * operational constants — import from config instead.
 *
 * Usage:
 *   import { config } from "@/config";
 *   if (file.size > config.upload.maxFileSizeBytes) { ... }
 *
 * Environment selection (in order of precedence):
 *   1. NEXT_PUBLIC_APP_ENV environment variable
 *   2. process.env.NODE_ENV  (Next.js sets this to "development" | "production" | "test")
 *   3. "development" (default)
 */

import development from "./development";
import testing from "./testing";
import production from "./production";

export interface AppConfig {
  env: "development" | "testing" | "production";

  upload: {
    /** Maximum file size in bytes */
    maxFileSizeBytes: number;
    /** Maximum number of entries in the upload queue */
    maxQueueEntries: number;
    /** Allowed MIME types for upload */
    allowedMimeTypes: string[];
    /** Timeout for presign request in ms */
    presignTimeoutMs: number;
    /** Timeout for file upload in ms */
    uploadTimeoutMs: number;
  };

  processing: {
    /** Maximum clips per processing job */
    maxClipsPerJob: number;
    /** Maximum retry attempts per job */
    maxRetries: number;
    /** Polling interval for job events in ms */
    pollingIntervalMs: number;
    /** WebSocket reconnect delay in ms */
    webSocketReconnectMs: number;
  };

  notifications: {
    /** Default duration per variant in ms */
    defaultDurationMs: {
      success: number;
      error: number;
      warning: number;
      info: number;
    };
  };

  storage: {
    /** Active storage provider key */
    provider: "local" | "r2" | "s3";
    /** Maximum bytes for localStorage fallback */
    maxLocalStorageBytes: number;
  };

  api: {
    /** Base URL for the API backend */
    baseUrl: string;
    /** Default request timeout in ms */
    requestTimeoutMs: number;
    /** Number of automatic retries on failure */
    retryCount: number;
  };
}

function resolveConfig(): AppConfig {
  const env =
    process.env.NEXT_PUBLIC_APP_ENV ??
    process.env.NODE_ENV ??
    "development";

  switch (env) {
    case "test":
    case "testing":
      return testing;
    case "production":
    case "prod":
      return production;
    case "development":
    default:
      return development;
  }
}

/** The resolved application configuration (singleton). */
export const config: AppConfig = resolveConfig();
