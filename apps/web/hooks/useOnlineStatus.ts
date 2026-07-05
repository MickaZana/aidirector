"use client";

/**
 * useOnlineStatus — tracks navigator.onLine and dispatches a toast when
 * connectivity changes. Returns `true` when online.
 */
import { useCallback, useEffect, useState } from "react";
import { toast } from "@/stores/toast-store";

export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(true);

  const handleOnline = useCallback(() => {
    setOnline(true);
    toast.success("Back online", "Connection restored.");
  }, []);

  const handleOffline = useCallback(() => {
    setOnline(false);
    toast.warning("You're offline", "Some features may be unavailable until reconnected.");
  }, []);

  useEffect(() => {
    // Initial state
    setOnline(navigator.onLine);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, [handleOnline, handleOffline]);

  return online;
}
