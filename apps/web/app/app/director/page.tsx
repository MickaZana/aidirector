"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { DirectorEmptyState } from "@/components/empty-states/DirectorEmptyState";

export default function DirectorIndexPage() {
  const router = useRouter();
  const { jobs, loading } = useRecentJobs();

  const handleSelectJob = useCallback(
    (jobId: string) => {
      router.push(`/app/director/${jobId}`);
    },
    [router],
  );

  return (
    <div className="flex items-center justify-center min-h-screen">
      {loading ? (
        <p className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>
          Loading pipelines…
        </p>
      ) : (
        <DirectorEmptyState jobs={jobs} onSelectJob={handleSelectJob} />
      )}
    </div>
  );
}
