"use client";

import { Surface } from "@/design-system/Surface";
import { ClipCard } from "@/components/clips/ClipCard";
import { useJobView } from "@/hooks/useJobView";
import type { SelectedCandidate } from "@/lib/api";

interface Props {
  jobId: string;
}

export function RankedClipsBoard({ jobId }: Props) {
  const { view, loading } = useJobView(jobId);

  if (loading || !view) {
    return (
      <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
        Loading clips…
      </Surface>
    );
  }

  const candidates = [...view.candidates].sort((a, b) => {
    const af = (a.scores.final_rank_score as number | undefined) ?? a.confidence_score ?? 0;
    const bf = (b.scores.final_rank_score as number | undefined) ?? b.confidence_score ?? 0;
    return bf - af;
  });

  const plan = view.director_plan;
  const selectionsById = new Map<string, SelectedCandidate>(
    plan?.selected_candidates.map(
      (s: SelectedCandidate) => [s.candidate_id, s] as [string, SelectedCandidate],
    ) ?? [],
  );

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Ranked clips</h2>
          <p className="text-sm text-[color:var(--color-text-secondary)] mt-0.5">
            Sorted by final rank score. Engagement-boosted clips show a pulsing accent badge.
          </p>
        </div>
      </header>

      {candidates.length === 0 ? (
        <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
          No candidates yet — ranking is still in flight.
        </Surface>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5">
          {candidates.map((c, i) => (
            <ClipCard
              key={c.id}
              rank={i + 1}
              candidate={c}
              selection={selectionsById.get(c.id)}
              href={`/app/director/${jobId}?clip=${c.id}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
