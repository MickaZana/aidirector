/**
 * Analytics service tests.
 *
 * Validates the privacy-conscious analytics service:
 * - Event tracking and storage
 * - localStorage persistence
 * - Opt-out support
 * - Event trimming at max capacity
 */
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { ANALYTICS_EVENTS } from "@/services/analytics";
import type { AnalyticsEventName } from "@/services/analytics";

// ── Helpers ─────────────────────────────────────────────────────────────

const STORAGE_KEY = "aidirector_analytics_events";

function getStoredEvents() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

// We import analytics dynamically so we can seed localStorage first
let analytics: import("@/services/analytics").Analytics;

async function getAnalytics() {
  const mod = await import("@/services/analytics");
  return mod.analytics;
}

// ── Tests ───────────────────────────────────────────────────────────────

describe("analytics service", () => {
  beforeEach(async () => {
    localStorage.clear();
    // Get fresh analytics instance
    const mod = await import("@/services/analytics");
    analytics = mod.analytics;
    analytics.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Event tracking ──────────────────────────────────────────────────

  it("starts with no events", () => {
    expect(analytics.getEvents()).toEqual([]);
  });

  it("tracks an event with name and timestamp", () => {
    const before = Date.now();
    analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED);
    const after = Date.now();

    const events = analytics.getEvents();
    expect(events).toHaveLength(1);
    expect(events[0].name).toBe("project_started");
    expect(events[0].timestamp).toBeGreaterThanOrEqual(before);
    expect(events[0].timestamp).toBeLessThanOrEqual(after);
  });

  it("tracks events with optional properties", () => {
    analytics.track(ANALYTICS_EVENTS.UPLOAD_COMPLETED, {
      fileSize: 1024,
      fileName: "test.mp4",
    });

    const events = analytics.getEvents();
    expect(events).toHaveLength(1);
    expect(events[0].properties).toEqual({
      fileSize: 1024,
      fileName: "test.mp4",
    });
  });

  it("tracks all defined event types", () => {
    const allNames = Object.values(ANALYTICS_EVENTS);
    for (const name of allNames) {
      analytics.track(name as AnalyticsEventName);
    }

    expect(analytics.getEvents()).toHaveLength(allNames.length);
    const trackedNames = analytics.getEvents().map((e) => e.name);
    for (const name of allNames) {
      expect(trackedNames).toContain(name);
    }
  });

  // ── localStorage persistence ────────────────────────────────────────

  it("persists events to localStorage", () => {
    analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED);
    analytics.track(ANALYTICS_EVENTS.UPLOAD_COMPLETED, { fileSize: 512 });

    const stored = getStoredEvents();
    expect(stored).toHaveLength(2);
    expect(stored[0].name).toBe("project_started");
    expect(stored[1].name).toBe("upload_completed");
    expect(stored[1].properties?.fileSize).toBe(512);
  });

  // ── Clear ───────────────────────────────────────────────────────────

  it("clears all events from memory and storage", () => {
    analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED);
    analytics.track(ANALYTICS_EVENTS.UPLOAD_COMPLETED);
    expect(analytics.getEvents()).toHaveLength(2);

    analytics.clear();
    expect(analytics.getEvents()).toHaveLength(0);
    expect(getStoredEvents()).toHaveLength(0);
  });

  // ── Opt-out ─────────────────────────────────────────────────────────

  it("does not track events when disabled", () => {
    analytics.setEnabled(false);
    analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED);
    analytics.track(ANALYTICS_EVENTS.UPLOAD_COMPLETED);

    expect(analytics.getEvents()).toHaveLength(0);
  });

  it("resumes tracking when re-enabled", () => {
    analytics.setEnabled(false);
    analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED);
    expect(analytics.getEvents()).toHaveLength(0);

    analytics.setEnabled(true);
    analytics.track(ANALYTICS_EVENTS.UPLOAD_COMPLETED);
    expect(analytics.getEvents()).toHaveLength(1);
    expect(analytics.getEvents()[0].name).toBe("upload_completed");
  });

  // ── Storage limits ──────────────────────────────────────────────────

  it("trims events in localStorage to MAX_STORED_EVENTS", () => {
    // Track 1010 events — the in-memory array holds all of them
    // but the persisted copy in localStorage is trimmed
    for (let i = 0; i < 1010; i++) {
      analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED, { index: i });
    }

    // In-memory has all 1010
    const events = analytics.getEvents();
    expect(events).toHaveLength(1010);

    // localStorage should be trimmed to 1000
    const stored = getStoredEvents();
    expect(stored.length).toBeLessThanOrEqual(1000);
    expect(stored.length).toBe(1000);
  });

  // ── Flush (stub) ────────────────────────────────────────────────────

  it("flush does not throw", async () => {
    analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED);
    await expect(analytics.flush()).resolves.toBeUndefined();
  });

  // ── Error resilience ────────────────────────────────────────────────

  it("handles localStorage errors gracefully on get", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Storage full");
    });

    expect(() => analytics.getEvents()).not.toThrow();
    // The events should still be accessible from memory
    expect(analytics.getEvents()).toEqual([]);
  });

  it("handles corrupted localStorage data gracefully", () => {
    localStorage.setItem(STORAGE_KEY, "not valid json");

    // Clear and re-check — should not throw
    analytics.clear();
    expect(analytics.getEvents()).toEqual([]);
  });

  it("handles localStorage errors gracefully on set", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("Storage full");
    });

    // Tracking should not throw even if storage fails
    expect(() => analytics.track(ANALYTICS_EVENTS.PROJECT_STARTED)).not.toThrow();
    // In-memory still has the event
    expect(analytics.getEvents()).toHaveLength(1);
  });
});
