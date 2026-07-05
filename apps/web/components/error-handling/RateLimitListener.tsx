"use client";

/**
 * RateLimitListener — listens for `rate-limited` custom DOM events
 * dispatched by the API client and shows a toast with a cooldown message.
 *
 * Place once in the root layout alongside the Toaster.
 */
import { useEffect, useRef } from "react";
import { RATE_LIMIT_EVENT, type RateLimitEventDetail } from "@/lib/api/client";
import { toast } from "@/stores/toast-store";

export function RateLimitListener() {
  const lastEvent = useRef(0);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<RateLimitEventDetail>).detail;
      // Deduplicate rapid repeated events (same or near-same time)
      const now = Date.now();
      if (now - lastEvent.current < 5_000) return;
      lastEvent.current = now;

      toast.warning(
        "Too many requests",
        `Rate limit reached. Try again in ${detail.retryAfterSeconds} second${detail.retryAfterSeconds === 1 ? "" : "s"}.`,
      );
    };

    window.addEventListener(RATE_LIMIT_EVENT, handler);
    return () => window.removeEventListener(RATE_LIMIT_EVENT, handler);
  }, []);

  return null;
}
