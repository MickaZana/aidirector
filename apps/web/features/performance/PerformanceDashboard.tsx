"use client";

import { Activity, BarChart3, GitMerge, LineChart, Shield, Sparkles } from "lucide-react";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { ProgressTrack } from "@/design-system/ProgressTrack";
import { StatusDot } from "@/design-system/StatusDot";
import { useJobView } from "@/hooks/useJobView";
import { cn } from "@/lib/cn";
import { formatPercent, formatScore, shortenHash, shortenId } from "@/lib/format";
import type { MaturityState, PerformanceFeatureView, RankingSnapshot } from "@/lib/api/types";

interface Props {
  jobId: string;
}

export function PerformanceDashboard({ jobId }: Props) {
  const { view, loading } = useJobView(jobId);

  if (loading || !view) {
    return (
      <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
        Loading performance signals…
      </Surface>
    );
  }

  const featureViews = view.feature_views;
  const snapshots = view.snapshots;

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Performance Feedback</h2>
          <p className="text-sm text-[color:var(--color-text-secondary)] mt-0.5 max-w-2xl">
            Derived engagement features feeding the ranker. Raw telemetry is intentionally
            hidden — only confidence-weighted, normalised, capped signals are visible here.
          </p>
        </div>
        <Badge tone="accent">trust-gradient verified</Badge>
      </header>

      <div className="grid lg:grid-cols-3 gap-5">
        <GuardCard
          icon={<Shield className="h-3.5 w-3.5 text-[color:var(--color-accent-green)]" />}
          label="Confidence threshold"
          value="0.30"
          hint="Below this, adjustment is 0. Spike-resistance gate."
        />
        <GuardCard
          icon={<BarChart3 className="h-3.5 w-3.5 text-[color:var(--color-accent-gold)]" />}
          label="Engagement weight cap"
          value="±0.15"
          hint="Maximum influence over [0,1] rank score."
        />
        <GuardCard
          icon={<GitMerge className="h-3.5 w-3.5 text-[color:var(--color-accent-blue)]" />}
          label="Feature version"
          value={featureViews[0]?.feature_version ?? "—"}
          hint="Evaluator schema generation."
        />
      </div>

      {/* Feature views (derived, ranker-safe) */}
      <Surface variant="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold tracking-tight uppercase tracking-[0.18em] text-[color:var(--color-text-secondary)]">
            Performance feature sets
          </h3>
          <Badge tone="muted">{featureViews.length} exports tracked</Badge>
        </div>
        {featureViews.length === 0 ? (
          <p className="text-sm text-[color:var(--color-text-tertiary)] text-center py-8">
            No engagement signals yet — exports need maturity before evaluation runs.
          </p>
        ) : (
          <div className="space-y-3">
            {featureViews.map((f: PerformanceFeatureView) => (
              <FeatureViewCard key={f.export_id} view={f} />
            ))}
          </div>
        )}
      </Surface>

      {/* Ranking snapshots (audit trail) */}
      <Surface variant="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold tracking-tight uppercase tracking-[0.18em] text-[color:var(--color-text-secondary)]">
            Ranking snapshots
          </h3>
          <span className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)]">
            audit · {snapshots.length} rows
          </span>
        </div>
        <div className="space-y-2">
          {snapshots.map((s: RankingSnapshot) => (
            <SnapshotRow key={s.id} snapshot={s} />
          ))}
        </div>
      </Surface>

      {/* Lineage tip */}
      <Surface variant="glass" dense className="flex items-center gap-3">
        <Sparkles className="h-4 w-4 text-[color:var(--color-accent-gold)] shrink-0" />
        <p className="text-xs text-[color:var(--color-text-secondary)]">
          The ranker reads <span className="font-mono text-[color:var(--color-text-primary)]">PerformanceFeatureView</span>{" "}
          (12 derived fields) only. Raw <span className="font-mono">engagement_events</span> rows
          are unreachable from the client — the trust gradient prevents reward-hacking by design.
        </p>
      </Surface>
    </div>
  );
}

function GuardCard({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: string; hint: string }) {
  return (
    <Surface variant="card">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
        {icon}
        {label}
      </div>
      <div className="mt-1 font-mono text-3xl tabular-nums">{value}</div>
      <p className="mt-1 text-xs text-[color:var(--color-text-tertiary)]">{hint}</p>
    </Surface>
  );
}

function FeatureViewCard({ view }: { view: PerformanceFeatureView }) {
  return (
    <div className="rounded-xl bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] p-4">
      <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-2">
          <StatusDot status={view.maturity_state} size="md" pulse={view.maturity_state === "stable"} />
          <span className="text-sm font-mono">{shortenId(view.export_id)}</span>
          <Badge status={view.maturity_state}>
            {view.maturity_state}
          </Badge>
        </div>
        <div className="flex items-center gap-3 text-[11px] uppercase tracking-wider text-[color:var(--color-text-tertiary)] font-mono">
          <span>confidence {formatScore(view.engagement_confidence)}</span>
          <span>·</span>
          <span>score {formatScore(view.engagement_score)}</span>
        </div>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <MetricBar label="views" value={view.normalized_view_rate} />
        <MetricBar label="completion" value={view.normalized_completion_rate} />
        <MetricBar label="watch time" value={view.normalized_watch_time} />
        <MetricBar label="replays" value={view.replay_rate} />
        <MetricBar label="shares" value={view.share_rate} />
      </div>
    </div>
  );
}

function MetricBar({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-text-tertiary)]">
        <span>{label}</span>
        <span className="font-mono tabular-nums">{value != null ? formatPercent(value) : "—"}</span>
      </div>
      <ProgressTrack value={value ?? 0} tone={value != null && value > 0.5 ? "accent" : "blue"} />
    </div>
  );
}

function SnapshotRow({ snapshot }: { snapshot: RankingSnapshot }) {
  return (
    <div className="rounded-lg bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] px-4 py-3 grid grid-cols-12 gap-3 items-center">
      <div className="col-span-12 md:col-span-3 flex items-center gap-2">
        <Activity className="h-3 w-3 text-[color:var(--color-text-tertiary)]" />
        <span className="font-mono text-xs">{shortenId(snapshot.candidate_id)}</span>
        <Badge status={snapshot.feedback_applied ? "stable" : "queued"}>
          {snapshot.feedback_applied ? "applied" : "skipped"}
        </Badge>
      </div>
      <div className="col-span-4 md:col-span-2 font-mono text-[11px] tabular-nums">
        <div className="text-[9px] uppercase text-[color:var(--color-text-tertiary)]">base</div>
        <div>{formatScore(snapshot.base_rank_score)}</div>
      </div>
      <div className="col-span-4 md:col-span-2 font-mono text-[11px] tabular-nums">
        <div className="text-[9px] uppercase text-[color:var(--color-text-tertiary)]">adjustment</div>
        <div
          className={cn(
            snapshot.engagement_adjustment > 0 && "text-[color:var(--color-accent-green)]",
            snapshot.engagement_adjustment < 0 && "text-[color:var(--color-accent-magenta)]",
          )}
        >
          {snapshot.engagement_adjustment > 0 ? "+" : ""}
          {formatScore(snapshot.engagement_adjustment)}
        </div>
      </div>
      <div className="col-span-4 md:col-span-2 font-mono text-[11px] tabular-nums">
        <div className="text-[9px] uppercase text-[color:var(--color-text-tertiary)]">final</div>
        <div className="text-[color:var(--color-accent-green)] font-semibold">
          {formatScore(snapshot.final_rank_score)}
        </div>
      </div>
      <div className="col-span-12 md:col-span-3 text-[11px] text-[color:var(--color-text-tertiary)] truncate" title={snapshot.explanation}>
        {snapshot.explanation}
      </div>
    </div>
  );
}
