"use client";

/**
 * useRecentJobs — lists jobs for the authenticated tenant.
 *
 * Fixture-mode and live-fallback semantics match `useJobView`:
 *   - `NEXT_PUBLIC_API_URL` unset / "fixtures" → serve fixtures, no network.
 *   - live mode → hit `/api/jobs`; on failure, surface the fixture and
 *     mark `fixturesUsed=true` so the UI can show a "demo data" banner.
 */
import { useEffect, useState } from "react";
import { Fixtures, type Job } from "@/lib/api";
import { useApi } from "@/lib/api/runtime";

export interface UseRecentJobsResult {
  jobs: Job[];
  loading: boolean;
  error: unknown;
  fixturesUsed: boolean;
}

export function useRecentJobs(): UseRecentJobsResult {
  const { endpoints, mode } = useApi();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [fixturesUsed, setFixturesUsed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const useFixture = () => {
      if (cancelled) return;
      setJobs(Fixtures.FIXTURE_JOBS);
      setFixturesUsed(true);
      setLoading(false);
    };

    if (mode === "fixtures" || !endpoints) {
      useFixture();
      return () => {
        cancelled = true;
      };
    }

    endpoints
      .listJobs()
      .then((data) => {
        if (cancelled) return;
        setJobs(data);
        setFixturesUsed(false);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e);
        useFixture();
      });

    return () => {
      cancelled = true;
    };
  }, [endpoints, mode]);

  return { jobs, loading, error, fixturesUsed };
}
