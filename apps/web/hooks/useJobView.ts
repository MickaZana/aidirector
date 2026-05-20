"use client";

/**
 * useJobView — single source of truth for everything one job exposes.
 *
 * Two-tier transport:
 *   1. Poll `/api/jobs/{id}/events` every 4s (cheap — counts only).
 *   2. When `revision` changes (or on first load), refetch the full
 *      `/api/jobs/{id}/view` composite.
 *
 * Components NEVER reach into fetch / setInterval themselves. They
 * consume this hook. The transport policy lives here, not in the
 * components — that's what keeps the frontend architecture firewall
 * intact (see `proof_of_work_phase9.md`).
 *
 * Fixture mode (`NEXT_PUBLIC_API_URL` unset or set to `"fixtures"`):
 *   bypasses the network and serves the in-repo fixture directly so the
 *   UI is demoable without a backend.
 *
 * Live-mode fallback: if a live call throws (DNS, 5xx, CORS in dev),
 * the hook surfaces the fixture and sets `fixturesUsed=true` so the UI
 * can show a "demo data" banner without breaking.
 */
import { useEffect, useRef, useState } from "react";
import { Fixtures, type JobEvents, type JobView, type PipelineStage } from "@/lib/api";
import { useApi } from "@/lib/api/runtime";
import { derivePipelineStages } from "@/services/pipeline-stages";

const POLL_INTERVAL_MS = 4_000;

export interface UseJobViewResult {
  view: JobView | null;
  stages: PipelineStage[];
  loading: boolean;
  error: unknown;
  fixturesUsed: boolean;
}

function fixtureFor(jobId: string): JobView {
  return {
    ...Fixtures.FIXTURE_JOB_VIEW,
    job: { ...Fixtures.FIXTURE_JOB_VIEW.job, id: jobId },
  };
}

export function useJobView(jobId: string | null): UseJobViewResult {
  const { endpoints, mode } = useApi();
  const [view, setView] = useState<JobView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [fixturesUsed, setFixturesUsed] = useState(false);
  const revisionRef = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId) {
      setView(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    setLoading(true);
    revisionRef.current = null;

    const useFixture = () => {
      if (cancelled) return;
      setView(fixtureFor(jobId));
      setFixturesUsed(true);
      setLoading(false);
    };

    if (mode === "fixtures" || !endpoints) {
      useFixture();
      return () => {
        cancelled = true;
      };
    }

    const refetchView = async () => {
      try {
        const next = await endpoints.getJobView(jobId);
        if (cancelled) return;
        setView(next);
        setFixturesUsed(false);
        setLoading(false);
      } catch (e) {
        if (cancelled) return;
        setError(e);
        // Fall back to fixture so the UI still renders something
        // recognisable in dev mode.
        if (view === null) useFixture();
        else setLoading(false);
      }
    };

    const pollEvents = async () => {
      if (cancelled) return;
      try {
        const events: JobEvents = await endpoints.getJobEvents(jobId);
        if (cancelled) return;
        if (revisionRef.current === null || events.revision !== revisionRef.current) {
          revisionRef.current = events.revision;
          await refetchView();
        }
      } catch (e) {
        if (cancelled) return;
        setError(e);
        if (view === null) useFixture();
      } finally {
        if (!cancelled) timer = setTimeout(pollEvents, POLL_INTERVAL_MS);
      }
    };

    void pollEvents();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, mode, endpoints]);

  return {
    view,
    stages: derivePipelineStages(view),
    loading,
    error,
    fixturesUsed,
  };
}
