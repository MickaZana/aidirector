"use client";

/**
 * useRateLimit — cooldown timer for rate-limited actions.
 *
 * When the API returns 429, call `triggerCooldown(retryAfter)` to disable
 * the associated button for `retryAfter` seconds. Returns `cooldownRemaining`
 * so the UI can show a countdown and disable the trigger.
 */
import { useCallback, useRef, useState } from "react";

export interface UseRateLimitResult {
  /** Seconds remaining before the action can be retried. 0 = no cooldown. */
  cooldownRemaining: number;
  /** Start a cooldown for `seconds`. */
  triggerCooldown: (seconds: number) => void;
  /** Reset the cooldown early. */
  resetCooldown: () => void;
}

export function useRateLimit(): UseRateLimitResult {
  const [cooldownRemaining, setCooldownRemaining] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const triggerCooldown = useCallback(
    (seconds: number) => {
      clearTimer();
      setCooldownRemaining(seconds);
      intervalRef.current = setInterval(() => {
        setCooldownRemaining((prev) => {
          if (prev <= 1) {
            clearTimer();
            return 0;
          }
          return prev - 1;
        });
      }, 1_000);
    },
    [clearTimer],
  );

  const resetCooldown = useCallback(() => {
    clearTimer();
    setCooldownRemaining(0);
  }, [clearTimer]);

  return { cooldownRemaining, triggerCooldown, resetCooldown };
}
