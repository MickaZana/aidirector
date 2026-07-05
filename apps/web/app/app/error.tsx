"use client";

import { useEffect } from "react";
import { AlertTriangle, Home, RefreshCw } from "lucide-react";
import Link from "next/link";

/**
 * App error boundary — catches unhandled errors inside the authenticated
 * app shell. Matches the cinematic dark design system and provides
 * navigation back to the safe starting point (/app/upload).
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("AppError caught:", error);
  }, [error]);

  return (
    <div
      className="flex items-center justify-center p-8 min-h-[60vh]"
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
          Something went wrong
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--color-text-secondary)" }}>
          This page encountered an error. Please try again or return to the upload studio.
        </p>
        <div className="flex items-center justify-center gap-3">
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
          <Link
            href="/app/upload"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: "var(--color-surface-2)",
              border: "1px solid var(--color-border-strong)",
              color: "var(--color-text-primary)",
            }}
          >
            <Home className="h-4 w-4" strokeWidth={2} />
            Go to upload
          </Link>
        </div>
      </div>
    </div>
  );
}
