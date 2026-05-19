"""Persist a RankedClipCandidates result to the clip_candidates table.

Used by:
- workers.clip_ranking_worker (after Modal-side ranking completes)
- the phase-3 local probe (drives the same path without Modal)

Links each candidate back to the originating Scene row (when
`CandidateRecord.scene_index` maps to a scene of the same job in input
order). Emits one CANDIDATE_CREATED event per row + one RANKING_COMPLETED
event for the batch, all in the same transaction.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from api.models import ClipCandidate, Job, Scene, UsageEventType
from api.services.intel.capability_registry import RankedClipCandidates
from api.services.usage_events import emit_usage_event


def persist_clip_candidates(
    db: Session,
    *,
    job: Job,
    scenes_in_order: list[Scene],
    ranked: RankedClipCandidates,
) -> list[ClipCandidate]:
    """Write one ClipCandidate row per ranked record + ranking usage events.

    `scenes_in_order` must be the same list of Scene rows passed into the
    ranker (so `CandidateRecord.scene_index` resolves back to the right
    Scene.id).
    """
    rows: list[ClipCandidate] = []
    for candidate in ranked.candidates:
        scene_row: Scene | None = None
        if candidate.scene_index is not None and 0 <= candidate.scene_index < len(scenes_in_order):
            scene_row = scenes_in_order[candidate.scene_index]

        row = ClipCandidate(
            id=uuid.uuid4(),
            job_id=job.id,
            tenant_id=job.tenant_id,
            scene_id=scene_row.id if scene_row is not None else None,
            t_start=candidate.t_start,
            t_end=candidate.t_end,
            confidence_score=candidate.confidence_score,
            quality_score=candidate.quality_score,
            platform_score=candidate.platform_score,
            virality_score=None,
            novelty_score=None,
            rationale=candidate.rationale,
            scores=candidate.scores,
        )
        db.add(row)
        rows.append(row)

        emit_usage_event(
            db,
            tenant_id=job.tenant_id,
            upload_id=job.upload_id,
            job_id=job.id,
            event_type=UsageEventType.CANDIDATE_CREATED,
            unit="candidate",
            metadata={
                "candidate_t_start": candidate.t_start,
                "candidate_t_end": candidate.t_end,
                "scene_id": str(scene_row.id) if scene_row is not None else None,
                "rank_score": candidate.scores.get("rank_score") if candidate.scores else None,
            },
        )
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.RANKING_COMPLETED,
        quantity=float(len(rows)),
        unit="ranking",
        metadata={
            "candidates_produced": len(rows),
            "ranking_engine": "OmegaClips.window_ranking",
        },
    )
    return rows
