"use client";

import { Download, Film, HardDrive, Hash } from "lucide-react";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { Button } from "@/design-system/Button";
import { StatusDot } from "@/design-system/StatusDot";
import { useJobView } from "@/hooks/useJobView";
import { formatBytes, formatRelativeTime, formatSeconds, shortenHash, shortenId } from "@/lib/format";
import type { ExportArtifact, RenderJob, RenderOutput, RenderJobStatus } from "@/lib/api/types";

interface Props {
  jobId: string;
}

export function RenderCenter({ jobId }: Props) {
  const { view, loading } = useJobView(jobId);

  if (loading || !view) {
    return (
      <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
        Loading render center…
      </Surface>
    );
  }

  const outputsByRenderJob = new Map<string, RenderOutput>();
  for (const out of view.render_outputs) outputsByRenderJob.set(out.render_job_id, out);

  const exportsByOutput = new Map<string, ExportArtifact>();
  for (const exp of view.exports) exportsByOutput.set(exp.render_output_id, exp);

  // Group render jobs by platform
  const byPlatform = new Map<string, RenderJob[]>();
  for (const rj of view.render_jobs) {
    const arr = byPlatform.get(rj.platform) ?? [];
    arr.push(rj);
    byPlatform.set(rj.platform, arr);
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold tracking-tight">Render & Export center</h2>
        <p className="text-sm text-[color:var(--color-text-secondary)] mt-0.5">
          Every variant the Director Plan produced, grouped by platform.
        </p>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard label="Render jobs" value={view.render_jobs.length} icon={<Film className="h-3 w-3" />} />
        <SummaryCard label="Render outputs" value={view.render_outputs.length} icon={<HardDrive className="h-3 w-3" />} />
        <SummaryCard label="Export artifacts" value={view.exports.length} icon={<Hash className="h-3 w-3" />} />
        <SummaryCard
          label="Total render"
          value={formatBytes(view.render_outputs.reduce((a: number, o) => a + (o.bytes ?? 0), 0))}
          icon={<Download className="h-3 w-3" />}
          mono
        />
      </div>

      {byPlatform.size === 0 ? (
        <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
          No renders yet. Pipeline is still in flight.
        </Surface>
      ) : (
        <div className="space-y-5">
          {[...byPlatform.entries()].map(([platform, jobs]) => (
            <Surface key={platform} variant="card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold tracking-tight capitalize">
                    {platform.replace(/_/g, " ")}
                  </h3>
                  <Badge tone="muted">{jobs.length} variants</Badge>
                </div>
                <span className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)]">
                  {platform === "youtube_shorts" || platform === "tiktok" || platform === "instagram_reels"
                    ? "9:16"
                    : "16:9"}
                </span>
              </div>
              <div className="space-y-3">
                {jobs.map((rj) => (
                  <RenderRow
                    key={rj.id}
                    job={rj}
                    output={outputsByRenderJob.get(rj.id)}
                    exportArtifact={
                      outputsByRenderJob.get(rj.id)
                        ? exportsByOutput.get(outputsByRenderJob.get(rj.id)!.id)
                        : undefined
                    }
                  />
                ))}
              </div>
            </Surface>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, icon, mono }: { label: string; value: number | string; icon?: React.ReactNode; mono?: boolean }) {
  return (
    <Surface variant="card" dense>
      <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)] flex items-center gap-1.5">
        {icon}
        {label}
      </div>
      <div className={`mt-1 text-2xl ${mono ? "font-mono" : "font-semibold"} tabular-nums`}>{value}</div>
    </Surface>
  );
}

function RenderRow({
  job,
  output,
  exportArtifact,
}: {
  job: RenderJob;
  output?: RenderOutput;
  exportArtifact?: ExportArtifact;
}) {
  return (
    <div className="rounded-xl bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] p-4 flex items-center gap-4">
      <div className="hidden sm:flex h-16 w-12 rounded-lg overflow-hidden bg-gradient-to-br from-[color:var(--color-surface-3)] to-[color:var(--color-surface-1)] items-center justify-center shrink-0">
        <Film className="h-5 w-5 text-[color:var(--color-text-tertiary)]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium font-mono">{exportArtifact?.filename ?? `render_${shortenId(job.id)}`}</span>
          <Badge status={renderStatusToKey(job.status)} pulse={job.status === "rendering"}>
            {job.status}
          </Badge>
          {job.pipeline && <Badge tone="muted">{job.pipeline.replace(/_/g, " ")}</Badge>}
        </div>
        <div className="mt-1 flex items-center gap-3 flex-wrap text-[11px] font-mono uppercase tracking-wider text-[color:var(--color-text-tertiary)]">
          <span>{output ? formatBytes(output.bytes) : "—"}</span>
          <span>{output ? formatSeconds(output.duration_s) : "—"}</span>
          <span>{output?.aspect_ratio ?? "—"}</span>
          {job.cost_cents != null && <span>${(job.cost_cents / 100).toFixed(2)}</span>}
          <span>{formatRelativeTime(job.finished_at ?? job.created_at)}</span>
        </div>
        {exportArtifact && (
          <div className="mt-2 grid gap-1 text-[10px] font-mono">
            <Lineage label="content_hash" value={exportArtifact.content_hash} />
            <Lineage label="export_hash" value={exportArtifact.export_hash} />
            <Lineage label="storage_uri" value={exportArtifact.storage_uri} truncate />
          </div>
        )}
      </div>
      <div className="flex flex-col gap-2 items-end shrink-0">
        <div className="flex items-center gap-1.5">
          <StatusDot status={renderStatusToKey(job.status)} size="sm" pulse={job.status === "rendering"} />
          {exportArtifact && (
            <Badge status="succeeded">
              v{exportArtifact.export_version}
            </Badge>
          )}
        </div>
        <Button variant="secondary" size="sm" disabled={!exportArtifact}>
          <Download className="h-3 w-3" /> Download
        </Button>
      </div>
    </div>
  );
}

function Lineage({ label, value, truncate }: { label: string; value: string; truncate?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-[color:var(--color-text-tertiary)]">
      <span className="uppercase tracking-wider text-[9px] w-20 shrink-0">{label}</span>
      <span className={`text-[color:var(--color-text-secondary)] ${truncate ? "truncate" : ""}`}>
        {truncate ? value : shortenHash(value)}
      </span>
    </div>
  );
}

function renderStatusToKey(status: RenderJobStatus): "queued" | "running" | "succeeded" | "failed" {
  if (status === "succeeded") return "succeeded";
  if (status === "failed") return "failed";
  if (status === "rendering") return "running";
  return "queued";
}
