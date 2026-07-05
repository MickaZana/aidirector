"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useRecentJobs } from "@/hooks/useRecentJobs";

export default function DirectorIndexPage() {
  const router = useRouter();
  const { jobs, loading } = useRecentJobs();

  useEffect(() => {
    if (loading) return;
    if (jobs.length > 0) {
      router.replace(`/app/director/${jobs[0].id}`);
    }
  }, [jobs, loading, router]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      {loading ? (
        <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
          Loading most recent pipeline…
        </p>
      ) : jobs.length === 0 ? (
        <div className="text-center space-y-4">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            No pipelines yet. Upload a match to get started.
          </p>
          <a
            href="/app/upload"
            className="inline-block text-sm font-medium px-4 py-2 rounded-lg"
            style={{ background: "var(--color-accent-green)", color: "var(--color-surface-0)" }}
          >
            Upload a match
          </a>
        </div>
      ) : null}
    </div>
  );
}
