"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

/**
 * Global error boundary — catches errors thrown in the root layout.
 * Required by Sentry to capture React rendering errors in App Router.
 *
 * This is intentionally spare (no external links) since the layout
 * itself may have failed to load.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("GlobalError caught:", error);
  }, [error]);

  return (
    <html>
      <body>
        <div
          className="flex items-center justify-center min-h-screen p-8"
          style={{ background: "var(--color-surface-0)" }}
        >
          <div className="max-w-sm w-full text-center">
            <div
              className="mx-auto h-14 w-14 rounded-full flex items-center justify-center mb-5"
              style={{ background: "rgba(255, 77, 141, 0.15)" }}
            >
              <AlertTriangle
                className="h-6 w-6"
                style={{ color: "var(--color-accent-magenta)" }}
                strokeWidth={2}
              />
            </div>
            <h1 className="text-lg font-semibold tracking-tight mb-1.5" style={{ color: "var(--color-text-primary)" }}>
              Critical error
            </h1>
            <p className="text-sm mb-6" style={{ color: "var(--color-text-secondary)" }}>
              The application encountered a critical error. Please try refreshing.
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
      </body>
    </html>
  );
}
