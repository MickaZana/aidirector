"""Adapter: clip ranking contract.

Wraps OmegaClips ranking (candidate_clip_selection, candidate_reel_ranking,
highlight_review_ranker) into a single AI Director contract.
"""
from __future__ import annotations

from api.services.intel.capability_registry import (
    CandidateRecord,
    RankedClipCandidates,
    SceneRecord,
)


def rank_clip_candidates_stub(
    upload_id: str, scenes: list[SceneRecord]
) -> RankedClipCandidates:
    """Stub — production impl lives in workers/clip_ranking_worker.py."""
    candidates = [
        CandidateRecord(
            scene_index=i,
            t_start=s.t_start,
            t_end=s.t_end,
            confidence_score=0.5,
            quality_score=0.5,
            platform_score=0.5,
            rationale="stub candidate from stub adapter",
            scores={"stub": True},
        )
        for i, s in enumerate(scenes)
    ]
    return RankedClipCandidates(upload_id=upload_id, candidates=candidates)
