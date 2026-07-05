"use client";

import { useEffect } from "react";
import { Clapperboard, RefreshCw } from "lucide-react";

/**
 * Root error boundary — catches unhandled errors on public pages
 * (marketing, privacy, terms). Provides a recover/retry UI so the
 * user never sees a white screen or raw stack trace.
 */
export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console in dev; Sentry captures in production
    console.error("RootError caught:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center p-8" style={{ background: "var(--color-surface-0)" }}>
      <div className="max-w-sm w-full text-center">
        <div className="relative mx-auto h-16 w-16 rounded-2xl bg-gradient-to-br from-[color:var(--color-accent-green)]/20 to-[color:var(--color-accent-blue)]/20 border border-[color:var(--color-border-accent)] flex items-center justify-center mb-6">
          <Clapperboard className="h-7 w-7 text-[color:var(--color-accent-green)]" strokeWidth={2} />
        </div>
        <h1 className="text-xl font-semibold tracking-tight mb-2" style={{ color: "var(--color-text-primary)" }}>
          Something went wrong
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--color-text-secondary)" }}>
          An unexpected error occurred. Our team has been notified.
        </p>
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
          style={{
            background: "var(--color-surface-2)",
            border: "1px solid var(--color-border-strong)",
            color: "var(--color-text-primary)",
          }}
        >
          <RefreshCw className="h-4 w-4" strokeWidth={2} />
          Try again
        </button>
      </div>
    </div>
  );
}
