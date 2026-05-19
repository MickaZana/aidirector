"use client";

/**
 * useJobView — single source of truth for everything one job exposes.
 *
 * Polling-backed today (4s interval), websocket-ready tomorrow.
 * Returns the most recent JobView snapshot the server has produced + a
 * derived pipeline-stages array. Components never poll; they consume
 * this hook.
 *
 * Until the backend ships `/api/jobs/{id}/view`, the hook falls back
 * to the in-repo fixture so the UI can be developed and demoed without
 * a live API.
 */
import { useEffect, useState } from "react";
import { Fixtures, type JobView } from "@/lib/api";
import { derivePipelineStages } from "@/services/pipeline-stages";
import type { PipelineStage } from "@/lib/api/types";

export interface UseJobViewResult {
  view: JobView | null;
  stages: PipelineStage[];
  loading: boolean;
  error: unknown;
}

export function useJobView(jobId: string | null): UseJobViewResult {
  const [view, setView] = useState<JobView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!jobId) {
      setView(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);

    // Fixture-mode: the dashboard composite route is Phase 9.5 work.
    // The shape matches what the live API will return.
    const v: JobView = { ...Fixtures.FIXTURE_JOB_VIEW, job: { ...Fixtures.FIXTURE_JOB_VIEW.job, id: jobId } };
    Promise.resolve(v)
      .then((next) => {
        if (cancelled) return;
        setView(next);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [jobId]);

  return {
    view,
    stages: derivePipelineStages(view),
    loading,
    error,
  };
}
