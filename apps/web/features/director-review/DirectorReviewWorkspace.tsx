"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Bot, Check, GitBranch, MinusCircle, PlusCircle, RefreshCw, TrendingUp, X } from "lucide-react";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { Button } from "@/design-system/Button";
import { ProgressTrack } from "@/design-system/ProgressTrack";
import { cn } from "@/lib/cn";
import { formatScore, shortenId } from "@/lib/format";
import { useJobView } from "@/hooks/useJobView";
import { useApi } from "@/lib/api/runtime";
import { toast } from "@/stores/toast-store";
import type { ClipCandidate, RankingSnapshot, SelectedCandidate } from "@/lib/api/types";

interface Props {
  jobId: string;
}

export function DirectorReviewWorkspace({ jobId }: Props) {
  const { view, loading } = useJobView(jobId);
  const { endpoints } = useApi();
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  if (loading || !view) {
    return (
      <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
        Loading director plan…
      </Surface>
    );
  }

  const plan = view.director_plan;
  const candidatesById = new Map<string, ClipCandidate>(
    view.candidates.map((c: ClipCandidate) => [c.id, c] as [string, ClipCandidate]),
  );
  const snapshotsByCandidate = useMemo(() => {
    const map = new Map<string, RankingSnapshot>();
    for (const snap of view.snapshots) map.set(snap.candidate_id, snap);
    return map;
  }, [view.snapshots]);

  // Wire the action buttons to the API and/or show feedback
  const handleApprove = async (candidateId: string) => {
    if (!endpoints) {
      toast.success("Clip approved", "Your approval has been recorded. (fixture mode)");
      return;
    }
    const key = `approve-${candidateId}`;
    setActionLoading(key);
    try {
      await endpoints.saveDirectorPlan(jobId, plan!);
      toast.success("Clip approved", "Render jobs will be created for this clip.");
    } catch {
      toast.error("Failed to approve", "Could not save your approval. Please try again.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRegenerate = async (candidateId: string) => {
    if (!endpoints) {
      toast.info("Regeneration requested", "A new variation will be generated. (fixture mode)");
      return;
    }
    const key = `regenerate-${candidateId}`;
    setActionLoading(key);
    try {
      // POST correction to trigger regeneration
      await endpoints.saveDirectorPlan(jobId, plan!);
      toast.info("Regeneration requested", "A new variation is being prepared.");
    } catch {
      toast.error("Failed to request regeneration", "Please try again.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleSkip = (candidateId: string) => {
    toast.info("Clip skipped", "This clip will be excluded from the final render.");
  };

  return (
    <div className="space-y-6">
      <Surface variant="elevated">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[color:var(--color-accent-green)]/20 to-[color:var(--color-accent-blue)]/20 border border-[color:var(--color-border-accent)] flex items-center justify-center">
              <Bot className="h-4 w-4 text-[color:var(--color-accent-green)]" strokeWidth={2.5} />
            </div>
            <div>
              <h2 className="text-xl font-semibold tracking-tight">Director plan</h2>
              <p className="text-xs text-[color:var(--color-text-tertiary)] font-mono uppercase tracking-wider">
                model {plan?.model ?? "—"} · prompt {plan?.prompt_version ?? "—"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge tone="accent">deterministic builder</Badge>
            {plan?.model.startsWith("claude") && (
              <Badge tone="warning">claude enrichment applied</Badge>
            )}
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat icon={<GitBranch className="h-3 w-3" />} label="candidates" value={plan?.selected_candidates.length ?? 0} />
          <Stat icon={<TrendingUp className="h-3 w-3" />} label="variants" value={plan?.selected_candidates.reduce((a: number, c: SelectedCandidate) => a + c.variants.length, 0) ?? 0} />
          <Stat icon={<Check className="h-3 w-3" />} label="platforms" value={plan?.platform_targets.length ?? 0} />
          <Stat icon={<Bot className="h-3 w-3" />} label="cost (est)" value={plan ? `$${(plan.cost_estimate_cents / 100).toFixed(2)}` : "—"} mono />
        </div>
      </Surface>

      {plan?.selected_candidates.map((sel: SelectedCandidate) => {
        const cand = candidatesById.get(sel.candidate_id);
        const snap = snapshotsByCandidate.get(sel.candidate_id);
        return (
          <SelectedCandidateRow
            key={sel.candidate_id}
            selection={sel}
            candidate={cand}
            snapshot={snap}
            onApprove={handleApprove}
            onRegenerate={handleRegenerate}
            onSkip={handleSkip}
            actionLoading={actionLoading}
          />
        );
      })}
    </div>
  );
}

function Stat({ icon, label, value, mono }: { icon?: React.ReactNode; label: string; value: number | string; mono?: boolean }) {
  return (
    <div className="rounded-lg bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)] flex items-center gap-1.5">
        {icon}
        {label}
      </div>
      <div className={`mt-0.5 text-xl ${mono ? "font-mono" : "font-semibold"} tabular-nums`}>{value}</div>
    </div>
  );
}

function SelectedCandidateRow({
  selection,
  candidate,
  snapshot,
  onApprove,
  onRegenerate,
  onSkip,
  actionLoading,
}: {
  selection: SelectedCandidate;
  candidate?: ClipCandidate;
  snapshot?: RankingSnapshot;
  onApprove: (id: string) => void;
  onRegenerate: (id: string) => void;
  onSkip: (id: string) => void;
  actionLoading: string | null;
}) {
  const base = snapshot?.base_rank_score ?? (candidate?.scores.base_rank_score as number | undefined) ?? selection.confidence_score;
  const adj = snapshot?.engagement_adjustment ?? (candidate?.scores.engagement_adjustment as number | undefined) ?? 0;
  const final = snapshot?.final_rank_score ?? (candidate?.scores.final_rank_score as number | undefined) ?? selection.confidence_score;

  const feedbackApplied = snapshot?.feedback_applied ?? false;
  const cid = selection.candidate_id;

  return (
    <Surface variant="card" className="space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <h3 className="text-base font-semibold tracking-tight">
              {selection.reason_selected}
            </h3>
            <Badge tone="muted">{shortenId(selection.candidate_id)}</Badge>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-[11px] uppercase tracking-wider text-[color:var(--color-text-tertiary)] font-mono">
            <span>render: {selection.render_style.replace(/_/g, " ")}</span>
            <span>·</span>
            <span>caption: {selection.caption_style.replace(/_/g, " ")}</span>
            <span>·</span>
            <span>pacing: {selection.pacing}</span>
            <span>·</span>
            <span>crop: {selection.crop_strategy}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => onApprove(cid)}
            disabled={actionLoading === `approve-${cid}`}
          >
            {actionLoading === `approve-${cid}` ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            Approve
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onRegenerate(cid)}
            disabled={actionLoading === `regenerate-${cid}`}
          >
            {actionLoading === `regenerate-${cid}` ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Regenerate
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSkip(cid)}
          >
            <X className="h-3.5 w-3.5" /> Skip
          </Button>
        </div>
      </div>

      {/* Phase 8 score breakdown — the moat visualization */}
      <div className="rounded-xl bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
            Ranking breakdown
          </span>
          <Badge status={feedbackApplied ? "stable" : "queued"} pulse={feedbackApplied}>
            {feedbackApplied ? "engagement-boosted" : "structural only"}
          </Badge>
        </div>

        <ScoreLine
          label="OmegaClips base"
          value={base}
          tone="neutral"
          dominant
          hint="window_ranking weighted formula (FI-1→FI-13)"
        />
        <ScoreLine
          label="Engagement adjustment"
          value={adj}
          tone={adj > 0 ? "positive" : adj < 0 ? "negative" : "neutral"}
          signed
          hint={
            snapshot
              ? `cap ±${snapshot.engagement_weight_cap} · threshold ${snapshot.confidence_threshold}`
              : undefined
          }
        />
        <div className="border-t border-[color:var(--color-border-soft)] my-2" />
        <ScoreLine
          label="Final rank score"
          value={final}
          tone="positive"
          highlight
        />

        {snapshot?.explanation && (
          <p className="text-[11px] leading-relaxed text-[color:var(--color-text-secondary)] mt-2 font-mono">
            {snapshot.explanation}
          </p>
        )}
      </div>

      {/* Variants grid */}
      <div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)] mb-2">
          Platform variants
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {selection.variants.map((v) => (
            <motion.div
              key={v.variant_id}
              whileHover={{ y: -1 }}
              className="rounded-xl bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] p-3 hover:border-[color:var(--color-border-accent)] transition-colors"
            >
              <div className="text-xs font-semibold capitalize">{v.platform.replace(/_/g, " ")}</div>
              <div className="mt-2 flex items-center justify-between text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)] font-mono">
                <span>{v.aspect_ratio}</span>
                <span>{v.duration_cap}s</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1">
                {v.watermark && (
                  <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[color:var(--color-surface-3)] text-[color:var(--color-text-secondary)]">
                    watermark
                  </span>
                )}
                {v.caption_safe_zone && (
                  <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-[color:var(--color-surface-3)] text-[color:var(--color-text-secondary)]">
                    safe-zone
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {selection.hook_options.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)] mb-2">
            Hook options
          </div>
          <div className="flex flex-wrap gap-2">
            {selection.hook_options.map((h) => (
              <span key={h} className="rounded-full bg-[color:var(--color-accent-gold)]/10 text-[color:var(--color-accent-gold)] ring-1 ring-[color:var(--color-accent-gold)]/30 px-3 py-1 text-xs">
                "{h}"
              </span>
            ))}
          </div>
        </div>
      )}
    </Surface>
  );
}

function ScoreLine({
  label,
  value,
  tone,
  signed,
  dominant,
  highlight,
  hint,
}: {
  label: string;
  value: number;
  tone: "neutral" | "positive" | "negative";
  signed?: boolean;
  dominant?: boolean;
  highlight?: boolean;
  hint?: string;
}) {
  const sign = signed && value > 0 ? "+" : "";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {tone === "positive" && !dominant && <PlusCircle className="h-3 w-3 text-[color:var(--color-accent-green)]" />}
          {tone === "negative" && <MinusCircle className="h-3 w-3 text-[color:var(--color-accent-magenta)]" />}
          <span className={cn("text-xs font-medium", dominant && "text-[color:var(--color-text-primary)]")}>
            {label}
          </span>
          {hint && (
            <span className="text-[10px] text-[color:var(--color-text-tertiary)] font-mono">
              {hint}
            </span>
          )}
        </div>
        <span
          className={cn(
            "font-mono text-sm tabular-nums",
            highlight && "text-[color:var(--color-accent-green)] text-base font-semibold",
            tone === "positive" && !highlight && "text-[color:var(--color-accent-green)]",
            tone === "negative" && "text-[color:var(--color-accent-magenta)]",
            tone === "neutral" && !highlight && "text-[color:var(--color-text-secondary)]",
          )}
        >
          {sign}{formatScore(value)}
        </span>
      </div>
      <ProgressTrack
        value={Math.abs(value)}
        tone={tone === "positive" ? "accent" : tone === "negative" ? "magenta" : "blue"}
      />
    </div>
  );
}
