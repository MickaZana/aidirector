/**
 * Privacy-conscious product analytics service.
 *
 * Design principles:
 * - No third-party libraries or cookies
 * - All data stored in localStorage (user-controlled)
 * - No personal identifiable information (PII) collected
 * - Users can clear data by clearing browser storage
 * - Future: flush to a first-party backend endpoint when available
 *
 * Usage:
 *   import { analytics } from "@/services/analytics";
 *   analytics.track("upload_completed", { fileSize: 12345 });
 */

// ── Event Names ─────────────────────────────────────────────

export const ANALYTICS_EVENTS = {
  PROJECT_STARTED: "project_started",
  UPLOAD_COMPLETED: "upload_completed",
  PROCESSING_STARTED: "processing_started",
  PROCESSING_COMPLETED: "processing_completed",
  CLIP_PREVIEW_OPENED: "clip_preview_opened",
  DOWNLOAD_CLICKED: "download_clicked",
  DOWNLOAD_ALL_CLICKED: "download_all_clicked",
  FAQ_OPENED: "faq_opened",
  HELP_CLICKED: "help_clicked",
  CANCEL_PROCESSING_USED: "cancel_processing_used",
  FEEDBACK_SUBMITTED: "feedback_submitted",
  UPLOAD_STARTED: "upload_started",
  UPLOAD_FAILED: "upload_failed",
  PROCESSING_FAILED: "processing_failed",
  SHARE_USED: "share_used",
  COPY_LINK_USED: "copy_link_used",
  NETWORK_FAILURE: "network_failure",
  OFFLINE_EVENT: "offline_event",
  PAGE_VIEWED: "page_viewed",
} as const;

export type AnalyticsEventName =
  (typeof ANALYTICS_EVENTS)[keyof typeof ANALYTICS_EVENTS];

// ── Event Types ─────────────────────────────────────────────

export interface AnalyticsEvent {
  /** Event name from ANALYTICS_EVENTS */
  name: AnalyticsEventName;
  /** Unix timestamp (ms) when the event occurred */
  timestamp: number;
  /** Optional event properties (non-PII only) */
  properties?: Record<string, unknown>;
}

// ── Service ─────────────────────────────────────────────────

const STORAGE_KEY = "aidirector_analytics_events";
const MAX_STORED_EVENTS = 1000;

class Analytics {
  private events: AnalyticsEvent[] = [];
  private enabled = true;

  constructor() {
    this.load();
  }

  // ── Public API ──────────────────────────────────────────

  /** Track a product event */
  track(
    name: AnalyticsEventName,
    properties?: Record<string, unknown>,
  ): void {
    if (!this.enabled) return;

    const event: AnalyticsEvent = {
      name,
      timestamp: Date.now(),
      properties,
    };

    this.events.push(event);
    this.persist();

    if (process.env.NODE_ENV === "development") {
      console.log(`[Analytics] ${name}`, properties ?? "");
    }
  }

  /** Get all stored events (for debugging / future flush) */
  getEvents(): AnalyticsEvent[] {
    return [...this.events];
  }

  /** Clear all stored events */
  clear(): void {
    this.events = [];
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Storage unavailable
    }
  }

  /** Toggle analytics collection (opt-out support) */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  /** Flush events to a backend endpoint (stub for future use) */
  async flush(): Promise<void> {
    // Future: POST to first-party backend endpoint
    // For now, just keep events in localStorage
    if (process.env.NODE_ENV === "development") {
      console.log(
        `[Analytics] Flush called — ${this.events.length} events queued`,
      );
    }
  }

  // ── Internal ────────────────────────────────────────────

  private persist(): void {
    try {
      // Keep only the most recent events
      const trimmed = this.events.slice(-MAX_STORED_EVENTS);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
    } catch {
      // localStorage full or unavailable — silently drop
    }
  }

  private load(): void {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as AnalyticsEvent[];
        if (Array.isArray(parsed)) {
          this.events = parsed;
        }
      }
    } catch {
      this.events = [];
    }
  }
}

/** Analytics class type for use in service registry */
export type { Analytics };

/** Singleton analytics instance */
export const analytics = new Analytics();
