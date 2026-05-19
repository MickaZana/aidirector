"use client";

import Link from "next/link";
import { TopBar } from "@/components/layout/TopBar";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { useRecentJobs } from "@/hooks/useRecentJobs";
import { formatCents, formatRelativeTime, shortenId } from "@/lib/format";

export default function JobsPage() {
  const { jobs, loading } = useRecentJobs();
  return (
    <>
      <TopBar
        title="Pipelines"
        subtitle="Every analysis job, ranking pass, director plan, render, and export"
      />
      <div className="px-6 lg:px-8 py-8 space-y-6">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight">Recent pipelines</h1>
          <p className="text-sm text-[color:var(--color-text-secondary)] mt-1">
            Each row is a job. Click through to see the full processing timeline.
          </p>
        </header>

        {loading ? (
          <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
            Loading jobs…
          </Surface>
        ) : (
          <div className="space-y-2">
            {jobs.map((j) => (
              <Link
                key={j.id}
                href={`/app/jobs/${j.id}` as never}
                className="block"
              >
                <Surface variant="card" dense interactive className="flex items-center gap-4">
                  <div className="font-mono text-xs text-[color:var(--color-text-tertiary)] w-24 shrink-0">
                    {shortenId(j.id)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium">{j.intent}</span>
                      <Badge
                        status={j.status === "succeeded" ? "succeeded" : j.status === "running" ? "running" : j.status === "failed" ? "failed" : "queued"}
                        pulse={j.status === "running"}
                      >
                        {j.status}
                      </Badge>
                    </div>
                    <div className="mt-1 text-[11px] font-mono uppercase tracking-wider text-[color:var(--color-text-tertiary)]">
                      {formatRelativeTime(j.created_at)} · cost {formatCents(j.cost_actual_cents)}
                    </div>
                  </div>
                </Surface>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
