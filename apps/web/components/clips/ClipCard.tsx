"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ChevronRight, Play, Trophy } from "lucide-react";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { ProgressTrack } from "@/design-system/ProgressTrack";
import { cn } from "@/lib/cn";
import { formatScore, formatSeconds, shortenId } from "@/lib/format";
import type { ClipCandidate, SelectedCandidate, Variant } from "@/lib/api/types";

interface Props {
  rank: number;
  candidate: ClipCandidate;
  selection?: SelectedCandidate;
  href?: string;
}

export function ClipCard({ rank, candidate, selection, href }: Props) {
  const scores = candidate.scores as Record<string, unknown>;
  const base = (scores.base_rank_score as number) ?? null;
  const adj = (scores.engagement_adjustment as number) ?? 0;
  const final = (scores.final_rank_score as number) ?? candidate.confidence_score ?? 0;
  const feedback = (scores.feedback_applied as boolean) ?? false;
  const explanation = scores.feedback_explanation as string | undefined;

  const card = (
    <Surface variant="card" interactive className="relative overflow-hidden">
      {/* Cinematic preview placeholder — broadcast-style frame */}
      <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-br from-[color:var(--color-surface-3)] via-[color:var(--color-surface-2)] to-[color:var(--color-surface-1)] overflow-hidden">
        <div className="absolute inset-0 opacity-30 bg-[radial-gradient(ellipse_at_center,_rgba(0,230,161,0.4),_transparent_60%)]" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-10 w-10 rounded-full bg-[color:var(--color-surface-glass)] backdrop-blur-sm border border-[color:var(--color-border-soft)] flex items-center justify-center">
            <Play className="h-4 w-4 text-[color:var(--color-text-primary)]" fill="currentColor" />
          </div>
        </div>
        <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded-full bg-black/60 backdrop-blur-sm px-2 py-0.5">
          <Trophy className="h-3 w-3 text-[color:var(--color-accent-gold)]" strokeWidth={2.5} />
          <span className="text-[10px] font-mono tracking-wider tabular-nums">#{rank}</span>
        </div>
        <div className="absolute top-3 right-3 font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-secondary)] bg-black/40 rounded px-1.5 py-0.5">
          {formatSeconds(candidate.t_end - candidate.t_start)}
        </div>
      </div>

      <div className="pt-32 pb-1 flex flex-col gap-3">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="text-sm font-semibold tracking-tight">
            {selection?.reason_selected?.split(";")[0] ?? candidate.rationale ?? "Goal moment"}
          </h3>
          <span className="font-mono text-[10px] text-[color:var(--color-text-tertiary)]">
            {shortenId(candidate.id)}
          </span>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Badge status={feedback ? "stable" : "queued"} pulse={feedback}>
            {feedback ? "engagement-boosted" : "base ranking"}
          </Badge>
          {selection && (
            <Badge tone="neutral">{selection.render_style.replace(/_/g, " ")}</Badge>
          )}
          {selection && (
            <Badge tone="muted">{selection.pacing} pacing</Badge>
          )}
        </div>

        {/* Score breakdown — the moat visualization */}
        <div className="grid grid-cols-3 gap-3 pt-1">
          <ScoreCell label="base" value={base ?? final} mono />
          <ScoreCell
            label="engagement"
            value={adj}
            tone={adj > 0 ? "positive" : adj < 0 ? "negative" : "neutral"}
            signed
          />
          <ScoreCell label="final" value={final} highlight />
        </div>

        <ProgressTrack value={final} tone={feedback ? "accent" : "blue"} showValue />

        {explanation && (
          <p className="text-[11px] leading-relaxed text-[color:var(--color-text-tertiary)] line-clamp-2">
            {explanation}
          </p>
        )}

        {selection && selection.variants.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap pt-1">
            {selection.variants.map((v) => (
              <VariantChip key={v.variant_id} variant={v} />
            ))}
          </div>
        )}
      </div>
    </Surface>
  );

  if (href) {
    return (
      <Link href={href as never} className="group block">
        <motion.div
          whileHover={{ y: -2 }}
          transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
        >
          {card}
        </motion.div>
      </Link>
    );
  }
  return card;
}

function ScoreCell({
  label,
  value,
  highlight,
  signed,
  tone = "neutral",
  mono,
}: {
  label: string;
  value: number;
  highlight?: boolean;
  signed?: boolean;
  tone?: "neutral" | "positive" | "negative";
  mono?: boolean;
}) {
  const sign = signed && value > 0 ? "+" : "";
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-[0.16em] text-[color:var(--color-text-tertiary)]">
        {label}
      </span>
      <span
        className={cn(
          mono && "font-mono",
          "text-base tabular-nums",
          highlight && "text-[color:var(--color-accent-green)] font-semibold",
          tone === "positive" && "text-[color:var(--color-accent-green)] font-semibold",
          tone === "negative" && "text-[color:var(--color-accent-magenta)] font-semibold",
          !highlight && tone === "neutral" && "text-[color:var(--color-text-secondary)]",
        )}
      >
        {sign}{formatScore(value)}
      </span>
    </div>
  );
}

function VariantChip({ variant }: { variant: Variant }) {
  const label = variant.platform.replace(/_/g, " ");
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-2)] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-[color:var(--color-text-secondary)]">
      {label}
      <ChevronRight className="h-2.5 w-2.5 opacity-50" />
      {variant.aspect_ratio}
    </span>
  );
}
