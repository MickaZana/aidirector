"""Clip ranking adapter — real OmegaClips integration with controlled
engagement feedback (Phase 3 + Phase 8).

Wraps OmegaClips's `rank_goal_candidate_windows_for_intent` ranking
pipeline. Phase 8 adds an optional `prior_performance` argument that
maps `scene_index → PerformanceFeatureView`. When supplied, the adapter
runs each candidate's `rank_score` through `apply_feedback_to_rank_score`
(see `ranking_feedback_adapter`) which applies a deterministic,
confidence-gated, capped adjustment.

Hard rules (enforced by import discipline + probe assertions):
  - NO `from api.models import EngagementEvent` here.
  - NO `from api.services.engagement_aggregation import …` here.
  - The ranker only ever reads `PerformanceFeatureView` (a frozen
    dataclass of 12 derived fields).
  - The OmegaClips `rank_score` is never overwritten — it's preserved
    as `base_rank_score` in the candidate's `scores` dict, and
    `final_rank_score` = `base_rank_score + engagement_adjustment`
    (clamped). `CandidateRecord.confidence_score` reflects the final
    score so downstream consumers see the adjusted value.
"""
from __future__ import annotations

import sys
from typing import Any

from api.services.intel.capability_registry import (
    CandidateRecord,
    RankedClipCandidates,
    SceneRecord,
)
from api.services.intel.omega_client import is_populated, submodule_path
from api.services.intel.ranking_feedback_adapter import (
    FeedbackOutcome,
    PerformanceFeatureView,
    apply_feedback_to_rank_score,
)

_INTEL_DIR = submodule_path()
if _INTEL_DIR.exists() and str(_INTEL_DIR) not in sys.path:
    sys.path.insert(0, str(_INTEL_DIR))


def rank_clip_candidates(
    upload_id: str,
    scenes: list[SceneRecord],
    *,
    ranking_intent: str = "goal_action",
    prior_performance: dict[int, PerformanceFeatureView] | None = None,
) -> RankedClipCandidates:
    """Rank scenes into clip candidates using real OmegaClips ranking,
    optionally applying controlled engagement feedback.

    Without `prior_performance` (the Phase 3 path): identical behaviour
    to before. Each candidate's `scores.rank_score` matches
    `scores.base_rank_score`; `engagement_adjustment` is 0;
    `feedback_applied` is False.

    With `prior_performance` mapping `scene_index → PerformanceFeatureView`
    (the Phase 8 path): for each ranked candidate, the matching view (if
    any) is passed to `apply_feedback_to_rank_score`. The structural
    `base_rank_score` is preserved verbatim. The adjustment is capped at
    ±`ENGAGEMENT_WEIGHT_CAP` (0.15) and zeroed when confidence is below
    `CONFIDENCE_THRESHOLD` (0.30). The final score is
    `clamp(0,1, base + adjustment)`; downstream consumers see it via
    `CandidateRecord.confidence_score` and `scores.rank_score`.
    """
    if not is_populated():
        raise RuntimeError(
            f"OmegaClips submodule not populated at {_INTEL_DIR}. "
            "Run `git submodule update --init --recursive`."
        )

    from football_pipeline.config import PipelineConfig
    from football_pipeline.window_ranking import rank_goal_candidate_windows_for_intent

    cfg = PipelineConfig()
    # Force-disable audio + shot-change CV for the fixture path; we feed
    # overrides explicitly.
    cfg.window_ranking_use_audio = False
    cfg.window_ranking_use_shot_change = False

    confirmed_score_changes, candidate_windows, shot_change_overrides = _scenes_to_ranker_inputs(scenes)

    if not candidate_windows:
        return RankedClipCandidates(upload_id=upload_id, candidates=[])

    report = rank_goal_candidate_windows_for_intent(
        ranking_intent=ranking_intent,
        video_path="fixture://memory",
        confirmed_score_changes=confirmed_score_changes,
        candidate_windows=candidate_windows,
        config=cfg,
        audio_signals=[],
        shot_change_overrides=shot_change_overrides,
    )

    return _report_to_candidates(
        upload_id, report, ranking_intent, prior_performance=prior_performance or {}
    )


def _scenes_to_ranker_inputs(
    scenes: list[SceneRecord],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[int, int], dict[str, float]],
]:
    """Build OmegaClips ranker inputs from AI Director scenes.

    One `confirmed_score_change` per scene and one `candidate_window` per
    scene (variant_rank=0 — we don't generate window variants here).
    Shot-change overrides are synthesized from the scene's intensity so the
    ranker doesn't open a video file.
    """
    confirmed_changes: list[dict[str, Any]] = []
    candidate_windows: list[dict[str, Any]] = []
    shot_change_overrides: dict[tuple[int, int], dict[str, float]] = {}

    for change_index, scene in enumerate(scenes):
        delta = scene.signals.get("scoreboard_delta", {}) or {}
        t_detected = float(scene.signals.get("t_detected", scene.t_start))
        t_confirmed = float(scene.signals.get("t_confirmed", scene.t_end))

        previous_score = (
            f"{delta.get('home_before', 0)}-{delta.get('away_before', 0)}"
        )
        new_score = (
            f"{delta.get('home_after', 0)}-{delta.get('away_after', 0)}"
        )

        confirmed_changes.append(
            {
                "change_index": change_index,
                "detected_at": t_detected,
                "confirmed_at": t_confirmed,
                "previous_score": previous_score,
                "new_score": new_score,
                "previous_start_time": max(0.0, t_detected - 30.0),
                "previous_end_time": t_detected,
                "new_start_time": t_confirmed,
                "new_end_time": t_confirmed + 30.0,
            }
        )

        candidate_windows.append(
            {
                "change_index": change_index,
                "variant_rank": 0,
                "window_type": "goal_action_window",
                "start_time": scene.t_start,
                "end_time": scene.t_end,
                "rationale": scene.signals.get(
                    "rationale", "scene → candidate window (variant 0)"
                ),
                "source_previous_score": previous_score,
                "source_new_score": new_score,
            }
        )

        # Synthesize shot-change density from scene intensity so ranking is
        # influenced by real OmegaClips signal-breakdown logic without
        # touching a video file.
        intensity = float(scene.intensity or 0.5)
        shot_change_overrides[(change_index, 0)] = {
            "score": round(min(1.0, intensity * 0.8), 3),
            "density": round(intensity * 0.4, 3),
            "active_transitions": 3,
            "sampled_transitions": 8,
        }

    return confirmed_changes, candidate_windows, shot_change_overrides


def _report_to_candidates(
    upload_id: str,
    report: dict[str, Any],
    ranking_intent: str,
    *,
    prior_performance: dict[int, PerformanceFeatureView],
) -> RankedClipCandidates:
    """Map OmegaClips ranker report → CandidateRecord list, optionally
    applying controlled engagement feedback per candidate."""
    candidates: list[CandidateRecord] = []
    for entry in report.get("candidate_windows_evaluated", []):
        breakdown = entry.get("signal_breakdown", {}) or {}
        rank = int(entry.get("rank", 0))
        rank_score = float(entry.get("rank_score", 0.0))
        change_index = int(entry.get("change_index", 0))

        # Phase 8: optionally apply controlled feedback. The view comes
        # from `ranking_feedback_adapter`, which itself only exposes
        # derived fields — raw events never reach this code path.
        view = prior_performance.get(change_index)
        outcome: FeedbackOutcome = apply_feedback_to_rank_score(rank_score, view)

        # base = what OmegaClips said (never overwritten in the scores dict)
        # final = base + capped, confidence-gated engagement adjustment
        base_rank_score = round(outcome.base_rank_score, 4)
        final_rank_score = round(outcome.final_rank_score, 4)

        # `confidence_score` and the legacy `rank_score` key both reflect
        # the FINAL score so downstream (director plan builder, etc.) sees
        # the adjusted value. The base is preserved separately for audit.
        confidence_score = round(min(1.0, max(0.0, final_rank_score)), 3)
        quality_score = round(
            min(
                1.0,
                0.5
                * (
                    float(breakdown.get("shot_change_score", 0.0))
                    + float(breakdown.get("tight_window_score", 0.0))
                ),
            ),
            3,
        )

        candidates.append(
            CandidateRecord(
                scene_index=change_index,
                t_start=float(entry.get("start_time", 0.0)),
                t_end=float(entry.get("end_time", 0.0)),
                confidence_score=confidence_score,
                quality_score=quality_score,
                platform_score=0.5,
                rationale=str(entry.get("ranking_explanation", "")),
                scores={
                    "rank": rank,
                    "rank_score": final_rank_score,        # legacy key = final
                    "base_rank_score": base_rank_score,    # what OmegaClips said
                    "engagement_adjustment": outcome.engagement_adjustment,
                    "final_rank_score": final_rank_score,
                    "feedback_applied": outcome.feedback_applied,
                    "feature_version": outcome.feature_version,
                    "confidence_threshold": outcome.confidence_threshold,
                    "engagement_weight_cap": outcome.engagement_weight_cap,
                    "feedback_explanation": outcome.explanation,
                    "feedback_breakdown": outcome.breakdown,
                    "ranking_intent": ranking_intent,
                    "ranking_engine": "OmegaClips.window_ranking",
                    "signal_breakdown": breakdown,
                    "source_previous_score": entry.get("source_previous_score"),
                    "source_new_score": entry.get("source_new_score"),
                    "blocker": report.get("blocker"),
                },
            )
        )

    return RankedClipCandidates(upload_id=upload_id, candidates=candidates)


def rank_clip_candidates_stub(
    upload_id: str, scenes: list[SceneRecord]
) -> RankedClipCandidates:
    """Legacy stub kept for tests that don't want OmegaClips imports."""
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
