"use client";

import { useEffect, useState } from "react";
import { Fixtures, type Job } from "@/lib/api";

export function useRecentJobs(): { jobs: Job[]; loading: boolean } {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    Promise.resolve(Fixtures.FIXTURE_JOBS).then((data) => {
      if (cancelled) return;
      setJobs(data);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return { jobs, loading };
}
