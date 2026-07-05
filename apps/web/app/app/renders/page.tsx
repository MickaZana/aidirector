"use client";

import { useSearchParams } from "next/navigation";
import { TopBar } from "@/components/layout/TopBar";
import { RenderCenter } from "@/features/render-center/RenderCenter";
import { RendersEmptyState } from "@/components/empty-states/RendersEmptyState";
import { useRecentJobs } from "@/hooks/useRecentJobs";

export default function RendersPage() {
  const searchParams = useSearchParams();
  const paramJobId = searchParams.get("jobId");

  const { jobs, loading } = useRecentJobs();
  const jobId = paramJobId ?? (jobs[0]?.id ?? null);

  // When there's a job but the RenderCenter shows no renders, the empty
  // state inside RenderCenter can show pipeline progress. For now, we
  // use a simplified check: if a job exists but there are no render
  // outputs, show the pipeline-aware empty state.
  const hasJobWithRenders = jobs.length > 0;

  return (
    <>
      <TopBar
        title="Render & Export Center"
        subtitle="Variant queue · render outputs · canonical export identity"
      />
      <div className="px-6 lg:px-8 py-8">
        {jobId ? (
          <RenderCenter jobId={jobId} />
        ) : loading ? (
          <div className="flex items-center justify-center h-64 text-sm" style={{ color: "var(--color-text-tertiary)" }}>
            Loading jobs…
          </div>
        ) : (
          <RendersEmptyState jobId={hasJobWithRenders ? jobs[0]?.id : null} />
        )}
      </div>
    </>
  );
}
