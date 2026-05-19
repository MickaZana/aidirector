"""Deterministic Director Plan builder.

The **authority** for DirectorPlan shape, candidate selection, timestamps,
duration caps, variants, aspect ratios, and pipeline compatibility. Claude
never owns these fields. The optional `director_agent_adapter` enrichment
layer may rewrite *content* (rationale, hook text) but cannot change shape.

The builder consumes already-persisted `ClipCandidate` rows so candidate IDs
are stable across the system. It produces a `DirectorPlan` that's already
validated through the Pydantic contract — any future enrichment is required
to re-validate before persistence.
"""
from __future__ import annotations

from typing import Iterable

from api.models import ClipCandidate
from api.schemas.director_plan import (
    AspectRatio,
    CaptionStyle,
    CropStrategy,
    DirectorPlan,
    Pacing,
    PlatformTarget,
    RenderStyle,
    SelectedCandidate,
    Variant,
)
from api.services.platform_optimizer import get_preset

# --- Defaults policy --------------------------------------------------------
#
# Centralised so changing a default is one edit and every consumer (worker,
# probe, future API) inherits it. Tuning these later does NOT affect schema
# stability — only the values that fill the shape change.

DEFAULT_MAX_CANDIDATES = 5
DEFAULT_MIN_CONFIDENCE = 0.2
DEFAULT_MIN_QUALITY = 0.0
DEFAULT_RENDER_STYLE: RenderStyle = "ffmpeg_basic"
DEFAULT_CROP_STRATEGY: CropStrategy = "action"
DEFAULT_DIRECTOR_MODEL = "deterministic-builder/v1"

# Per-variant cost estimate (deterministic guess for the budget gate).
_PER_VARIANT_COST_CENTS = 3


def build_director_plan(
    *,
    upload_id: str,
    job_id: str,
    candidates: Iterable[ClipCandidate],
    platform_targets: list[PlatformTarget],
    user_preferences: dict | None = None,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
) -> DirectorPlan:
    """Build a validated DirectorPlan from ranked candidates.

    Selection is deterministic: filter by confidence/quality thresholds,
    sort by rank (or confidence as fallback), take up to `max_candidates`.

    Each surviving candidate gets:
      - a `SelectedCandidate` with safe default pacing/caption/crop/render
      - one `Variant` per requested platform target, with aspect ratio
        and duration cap pulled from `platform_optimizer.PLATFORM_PRESETS`

    Validation: the returned `DirectorPlan` is constructed through Pydantic
    so any drift from the contract raises at build time, not at persist time.
    """
    user_preferences = user_preferences or {}

    selected = _select_top_candidates(
        candidates,
        max_candidates=max_candidates,
        min_confidence=float(
            user_preferences.get("min_confidence", DEFAULT_MIN_CONFIDENCE)
        ),
        min_quality=float(user_preferences.get("min_quality", DEFAULT_MIN_QUALITY)),
    )

    selected_candidates: list[SelectedCandidate] = []
    for cand in selected:
        variants = _build_variants_for_platforms(cand, platform_targets)
        selected_candidates.append(
            SelectedCandidate(
                candidate_id=str(cand.id),
                reason_selected=_default_reason(cand),
                confidence_score=_clamp_unit(cand.confidence_score),
                quality_score=_clamp_unit(cand.quality_score),
                platform_score=_clamp_unit(cand.platform_score),
                clip_start=float(cand.t_start),
                clip_end=float(cand.t_end),
                duration=max(0.5, float(cand.t_end) - float(cand.t_start)),
                pacing=_default_pacing(cand),
                caption_style=_default_caption_style(cand),
                crop_strategy=DEFAULT_CROP_STRATEGY,
                render_style=DEFAULT_RENDER_STYLE,
                hook_options=[],
                variants=variants,
            )
        )

    cost_estimate = sum(len(c.variants) for c in selected_candidates) * _PER_VARIANT_COST_CENTS

    return DirectorPlan(
        upload_id=upload_id,
        job_id=job_id,
        model=DEFAULT_DIRECTOR_MODEL,
        prompt_version="v1",
        platform_targets=platform_targets,
        selected_candidates=selected_candidates,
        cost_estimate_cents=cost_estimate,
    )


# --- Internals --------------------------------------------------------------


def _select_top_candidates(
    candidates: Iterable[ClipCandidate],
    *,
    max_candidates: int,
    min_confidence: float,
    min_quality: float,
) -> list[ClipCandidate]:
    surviving = [
        c
        for c in candidates
        if (c.confidence_score or 0.0) >= min_confidence
        and (c.quality_score or 0.0) >= min_quality
    ]
    surviving.sort(key=_candidate_sort_key, reverse=True)
    return surviving[:max_candidates]


def _candidate_sort_key(c: ClipCandidate) -> tuple[float, float, float]:
    """Highest first. Tiebreaker on quality, then platform score."""
    return (
        float(c.confidence_score or 0.0),
        float(c.quality_score or 0.0),
        float(c.platform_score or 0.0),
    )


def _clamp_unit(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def _default_pacing(c: ClipCandidate) -> Pacing:
    confidence = float(c.confidence_score or 0.0)
    if confidence >= 0.6:
        return "fast"
    if confidence >= 0.3:
        return "medium"
    return "slow"


def _default_caption_style(c: ClipCandidate) -> CaptionStyle:
    # Today, every scene we surface is a goal-event scene from FI-8 confirmation
    # (capability map #3). Sports-hype is the safe default for that.
    # Multi-vertical phase will branch on scene.kind.
    scene_kind = (c.scores or {}).get("scene_kind") if c.scores else None
    if scene_kind in (None, "goal", "highlight"):
        return "sports_hype"
    return "minimal"


def _default_reason(c: ClipCandidate) -> str:
    if c.rationale:
        return c.rationale
    return (
        f"selected by deterministic builder; rank_score="
        f"{(c.scores or {}).get('rank_score')}"
    )


def _build_variants_for_platforms(
    candidate: ClipCandidate, platform_targets: list[PlatformTarget]
) -> list[Variant]:
    variants: list[Variant] = []
    for index, platform in enumerate(platform_targets, start=1):
        preset = get_preset(platform)
        variants.append(
            Variant(
                variant_id=_stable_variant_id(candidate.id, platform, index),
                platform=platform,
                aspect_ratio=_aspect(preset["aspect_ratio"]),
                duration_cap=int(preset["duration_cap_s"]),
                caption_safe_zone=True,
                watermark=True,
            )
        )
    return variants


def _stable_variant_id(candidate_id, platform: PlatformTarget, index: int) -> str:
    short = str(candidate_id).split("-")[0]
    return f"{short}-{platform}-v{index}"


def _aspect(value: str) -> AspectRatio:
    # Trust the preset; runtime validation will catch invalid combinations.
    if value not in ("9:16", "1:1", "16:9"):
        raise ValueError(f"Unsupported aspect ratio from preset: {value}")
    return value  # type: ignore[return-value]
