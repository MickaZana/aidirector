/**
 * Application configuration tests.
 *
 * Validates:
 * - Config resolution for different environments
 * - Production config values (hard limits that affect beta users)
 * - Development config values
 * - Testing config values
 * - Config interface contract (all required fields present)
 */
import { describe, it, expect } from "vitest";
import { config, type AppConfig } from "@/config";
import development from "@/config/development";
import testing from "@/config/testing";
import production from "@/config/production";

// ── Tests ───────────────────────────────────────────────────────────────

describe("config resolution", () => {
  it("resolves to a known environment", () => {
    expect(["development", "testing", "production"]).toContain(config.env);
  });

  it("has production config object", () => {
    expect(production.env).toBe("production");
  });

  it("has development config object", () => {
    expect(development.env).toBe("development");
  });

  it("has testing config object", () => {
    expect(testing.env).toBe("testing");
  });
});

describe("production config", () => {
  it("allows 3 GB max upload", () => {
    expect(production.upload.maxFileSizeBytes).toBe(3 * 1024 * 1024 * 1024);
  });

  it("allows 12 queue entries", () => {
    expect(production.upload.maxQueueEntries).toBe(12);
  });

  it("allows all required video MIME types", () => {
    expect(production.upload.allowedMimeTypes).toContain("video/mp4");
    expect(production.upload.allowedMimeTypes).toContain("video/quicktime");
    expect(production.upload.allowedMimeTypes).toContain("video/x-msvideo");
    expect(production.upload.allowedMimeTypes).toContain("video/x-matroska");
    expect(production.upload.allowedMimeTypes).toContain("video/webm");
  });

  it("has 10 min upload timeout", () => {
    expect(production.upload.uploadTimeoutMs).toBe(600_000);
  });

  it("allows 12 clips per job", () => {
    expect(production.processing.maxClipsPerJob).toBe(12);
  });

  it("has 3 max retries", () => {
    expect(production.processing.maxRetries).toBe(3);
  });

  it("has R2 storage provider", () => {
    expect(production.storage.provider).toBe("r2");
  });

  it("has a valid API base URL", () => {
    expect(production.api.baseUrl).toBeDefined();
    expect(production.api.baseUrl.length).toBeGreaterThan(0);
  });

  it("has 30s API request timeout", () => {
    expect(production.api.requestTimeoutMs).toBe(30_000);
  });

  it("has 2 API retries", () => {
    expect(production.api.retryCount).toBe(2);
  });

  it("has notification durations for all variants", () => {
    expect(production.notifications.defaultDurationMs.success).toBeGreaterThan(0);
    expect(production.notifications.defaultDurationMs.error).toBeGreaterThan(0);
    expect(production.notifications.defaultDurationMs.warning).toBeGreaterThan(0);
    expect(production.notifications.defaultDurationMs.info).toBeGreaterThan(0);
  });
});

describe("development config", () => {
  it("has local storage provider in dev", () => {
    expect(development.storage.provider).toBe("local");
  });

  it("has 500 MB max upload in dev", () => {
    expect(development.upload.maxFileSizeBytes).toBe(500 * 1024 * 1024);
  });
});

describe("testing config", () => {
  it("has fast polling interval", () => {
    expect(testing.processing.pollingIntervalMs).toBe(500);
  });

  it("has 0 API retries", () => {
    expect(testing.api.retryCount).toBe(0);
  });

  it("has local storage provider", () => {
    expect(testing.storage.provider).toBe("local");
  });
});

describe("AppConfig interface contract", () => {
  it("all configs have all required fields", () => {
    const configs = [development, testing, production];
    for (const cfg of configs) {
      expect(cfg.upload.maxFileSizeBytes).toBeGreaterThan(0);
      expect(cfg.upload.allowedMimeTypes.length).toBeGreaterThan(0);
      expect(cfg.processing.pollingIntervalMs).toBeGreaterThan(0);
      expect(cfg.api.baseUrl).toBeDefined();
      expect(cfg.storage.provider).toBeDefined();
    }
  });
});
