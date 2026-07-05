"use client";

/**
 * OfflineBanner — shown when the browser reports the user is offline.
 * Listens to `online` / `offline` events and displays a persistent
 * banner at the top of the viewport.
 */
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { WifiOff } from "lucide-react";

export function OfflineBanner() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    setOffline(!navigator.onLine);
    const handleOffline = () => setOffline(true);
    const handleOnline = () => setOffline(false);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);
    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  return (
    <AnimatePresence>
      {offline && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="overflow-hidden"
        >
          <div className="flex items-center justify-center gap-2 px-4 py-2 bg-[color:var(--color-status-failed)]/10 border-b border-[color:var(--color-status-failed)]/20 text-xs text-[color:var(--color-status-failed)] font-medium">
            <WifiOff className="h-3.5 w-3.5" strokeWidth={2} />
            <span>You&apos;re offline. Some features may be unavailable.</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
