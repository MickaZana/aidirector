"use client";

/**
 * Enhanced empty state for the Director page.
 *
 * Shows a job selector when there are recent jobs, so the user doesn't
 * land on a blank page when the auto-redirect doesn't match what they
 * expect. When there are no jobs, shows the upload CTA.
 */
import { motion } from "framer-motion";
import { Clapperboard, Upload, ArrowRight } from "lucide-react";
import { Button } from "@/design-system/Button";
import { Badge } from "@/design-system/Badge";
import { formatRelativeTime, shortenId } from "@/lib/format";
import type { Job } from "@/lib/api";

interface DirectorEmptyStateProps {
  jobs: Job[];
  onSelectJob: (jobId: string) => void;
}

export function DirectorEmptyState({ jobs, onSelectJob }: DirectorEmptyStateProps) {
  if (jobs.length > 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
        className="max-w-xl mx-auto py-16 px-6"
      >
        <div className="text-center mb-8 space-y-2">
          <h2 className="text-xl font-semibold tracking-tight">Select a pipeline</h2>
          <p className="text-sm text-[color:var(--color-text-secondary)]">
            Choose a job to review its Director Plan — see which clips were selected,
            why, and what variants were produced.
          </p>
        </div>

        <div className="space-y-2">
          {jobs.slice(0, 10).map((job) => (
            <button
              key={job.id}
              onClick={() => onSelectJob(job.id)}
              className="w-full flex items-center justify-between gap-4 rounded-lg border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)] px-4 py-3 text-left transition-all hover:border-[color:var(--color-border-accent)] hover:bg-[color:var(--color-surface-2)] group"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="h-8 w-8 rounded-lg bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] flex items-center justify-center shrink-0">
                  <Clapperboard className="h-4 w-4 text-[color:var(--color-text-secondary)]" strokeWidth={1.5} />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">
                    Job {shortenId(job.id)}
                  </div>
                  <div className="text-[11px] text-[color:var(--color-text-tertiary)] font-mono">
                    {formatRelativeTime(job.created_at)}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <Badge
                  status={
                    job.status === "succeeded" ? "succeeded" :
                    job.status === "running" ? "running" :
                    job.status === "failed" ? "failed" : "queued"
                  }
                >
                  {job.status}
                </Badge>
                <ArrowRight className="h-4 w-4 text-[color:var(--color-text-tertiary)] group-hover:text-[color:var(--color-accent-green)] transition-colors" />
              </div>
            </button>
          ))}
        </div>
      </motion.div>
    );
  }

  // No jobs at all
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex flex-col items-center justify-center h-[60vh] gap-6"
    >
      <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-[color:var(--color-accent-green)]/15 to-[color:var(--color-accent-blue)]/10 border border-[color:var(--color-border-accent)] flex items-center justify-center shadow-[0_0_80px_-20px_rgba(0,230,161,0.3)]">
        <Clapperboard className="h-10 w-10 text-[color:var(--color-accent-green)]" strokeWidth={1.5} />
      </div>

      <div className="text-center max-w-sm space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">No pipelines yet</h2>
        <p className="text-sm text-[color:var(--color-text-secondary)] leading-relaxed">
          Upload a match to start a pipeline. The Director Agent selects the best
          moments, decides the edit style, and produces platform-ready clips.
        </p>
      </div>

      <a href="/app/upload">
        <Button variant="primary" size="lg">
          <Upload className="h-4 w-4" />
          Upload a match
        </Button>
      </a>
    </motion.div>
  );
}
