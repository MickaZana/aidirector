"use client";

/**
 * PipelineErrorCard — shows which stage failed with an error message and
 * a retry action. Used inside the ProcessingTimeline when a job has failed.
 */
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Surface } from "@/design-system/Surface";
import { Button } from "@/design-system/Button";
import type { PipelineStage } from "@/lib/api";

interface PipelineErrorCardProps {
  /** The job ID for retry navigation. */
  jobId: string;
  /** The pipeline stage that failed, if known. */
  failedStage?: PipelineStage | null;
  /** Human-readable error message from the job. */
  errorMessage?: string | null;
}

export function PipelineErrorCard({ jobId, failedStage, errorMessage }: PipelineErrorCardProps) {
  return (
    <Surface variant="card" className="border-[color:var(--color-status-failed)]/30">
      <div className="flex items-start gap-4">
        <div className="h-10 w-10 rounded-xl bg-[color:var(--color-status-failed)]/10 border border-[color:var(--color-status-failed)]/20 flex items-center justify-center shrink-0">
          <AlertTriangle className="h-5 w-5 text-[color:var(--color-status-failed)]" strokeWidth={2} />
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <h3 className="text-sm font-semibold text-[color:var(--color-status-failed)]">
            Pipeline failed
          </h3>
          {failedStage && (
            <p className="text-xs text-[color:var(--color-text-secondary)]">
              Failed at stage: <span className="font-mono text-[color:var(--color-text-primary)]">{failedStage.label}</span>
            </p>
          )}
          {errorMessage && (
            <p className="text-xs text-[color:var(--color-text-tertiary)] font-mono mt-1 p-2 rounded-md bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)]">
              {errorMessage}
            </p>
          )}
          <div className="flex items-center gap-2 mt-3">
            <a href={`/app/upload?retry=${jobId}`}>
              <Button variant="primary" size="sm">
                <RefreshCw className="h-3.5 w-3.5" />
                Retry pipeline
              </Button>
            </a>
            <a href="/app/upload">
              <Button variant="ghost" size="sm">
                Upload a new match
              </Button>
            </a>
          </div>
        </div>
      </div>
    </Surface>
  );
}
