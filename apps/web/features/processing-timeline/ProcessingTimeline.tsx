"use client";

import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { PipelineStageNode } from "@/components/pipeline/PipelineStageNode";
import { useJobView } from "@/hooks/useJobView";
import { currentStage } from "@/services/pipeline-stages";
import { formatRelativeTime, shortenHash, shortenId } from "@/lib/format";

interface Props {
  jobId: string;
}

export function ProcessingTimeline({ jobId }: Props) {
  const { view, stages, loading } = useJobView(jobId);

  if (loading || !view) {
    return (
      <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
        Loading pipeline…
      </Surface>
    );
  }

  const active = currentStage(stages);
  const totalElapsed = stages.reduce((acc, s) => acc + (s.elapsed_seconds ?? 0), 0);

  return (
    <div className="space-y-6">
      <Surface variant="elevated">
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{view.upload.filename}</h2>
            <p className="text-xs text-[color:var(--color-text-tertiary)] mt-1 font-mono uppercase tracking-wider">
              job <span className="text-[color:var(--color-text-secondary)]">{shortenId(view.job.id)}</span>
              {" · "}intel <span className="text-[color:var(--color-text-secondary)]">{shortenHash(view.job.intel_submodule_sha, 7)}</span>
              {" · "}created {formatRelativeTime(view.job.created_at)}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge
              status={view.job.status === "succeeded" ? "succeeded" : view.job.status === "running" ? "running" : view.job.status === "failed" ? "failed" : "queued"}
              pulse={view.job.status === "running"}
            >
              {view.job.status}
            </Badge>
            <span className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)]">
              active stage: {active.label}
            </span>
          </div>
        </div>

        {/* Summary metrics */}
        <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-3">
          <Metric label="Scenes" value={view.scenes.length} />
          <Metric label="Candidates" value={view.candidates.length} />
          <Metric label="Variants" value={view.director_plan ? view.director_plan.selected_candidates.reduce((a: number, c) => a + c.variants.length, 0) : 0} />
          <Metric label="Exports" value={view.exports.length} />
          <Metric label="Cost" value={`$${(view.job.cost_actual_cents / 100).toFixed(2)}`} mono />
        </div>
      </Surface>

      <Surface variant="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold tracking-tight uppercase tracking-[0.18em] text-[color:var(--color-text-secondary)]">
            Processing timeline
          </h3>
          <span className="font-mono text-[11px] text-[color:var(--color-text-tertiary)] tabular-nums">
            {totalElapsed > 0 ? `${totalElapsed.toFixed(1)}s total` : "—"}
          </span>
        </div>
        <div className="space-y-0">
          {stages.map((stage, i) => (
            <PipelineStageNode
              key={stage.key}
              stage={stage}
              index={i}
              isLast={i === stages.length - 1}
            />
          ))}
        </div>
      </Surface>
    </div>
  );
}

function Metric({ label, value, mono }: { label: string; value: number | string; mono?: boolean }) {
  return (
    <div className="rounded-lg bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
        {label}
      </div>
      <div className={`mt-0.5 text-xl ${mono ? "font-mono" : "font-semibold"} tabular-nums`}>
        {value}
      </div>
    </div>
  );
}
