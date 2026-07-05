"use client";

import { useSearchParams } from "next/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { PerformanceDashboard } from "@/features/performance/PerformanceDashboard";
import { useRecentJobs } from "@/hooks/useRecentJobs";

export default function PerformancePage() {
  const searchParams = useSearchParams();
  const paramJobId = searchParams.get("jobId");

  const { jobs, loading } = useRecentJobs();
  const jobId = paramJobId ?? (jobs[0]?.id ?? null);

  return (
    <>
      <TopBar
        title="Performance Feedback"
        subtitle="Trust-gradient evaluation · maturity · ranking snapshot audit"
      />
      <div className="px-6 lg:px-8 py-8">
        {jobId ? (
          <PerformanceDashboard jobId={jobId} />
        ) : loading ? (
          <div className="flex items-center justify-center h-64 text-sm" style={{ color: "var(--color-text-tertiary)" }}>
            Loading jobs…
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              No performance data yet. Complete a pipeline to see engagement stats.
            </p>
            <a
              href="/app/upload"
              className="text-sm font-medium px-4 py-2 rounded-lg"
              style={{ background: "var(--color-accent-green)", color: "var(--color-surface-0)" }}
            >
              Upload a match
            </a>
          </div>
        )}
      </div>
    </>
  );
}
