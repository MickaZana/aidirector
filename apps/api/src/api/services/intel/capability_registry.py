"""Contracts the AI Director uses to call OmegaClips.

Adapters in this package implement these. Workers invoke adapters; routers
never touch OmegaClips internals.
"""
from __future__ import annotations

from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.director_plan import (
    DirectorPlan,
    PlatformTarget,
    RenderResult,
    SelectedCandidate,
    Variant,
)


class SceneRecord(BaseModel):
    """One scene from OmegaClips analysis output."""
    model_config = ConfigDict(extra="forbid")

    t_start: float
    t_end: float
    kind: str
    arc_position: str | None = None
    intensity: float | None = None
    importance: float | None = None
    signals: dict[str, Any] = Field(default_factory=dict)


class CandidateRecord(BaseModel):
    """One ranked candidate clip."""
    model_config = ConfigDict(extra="forbid")

    scene_index: int | None = None
    t_start: float
    t_end: float
    confidence_score: float | None = None
    quality_score: float | None = None
    platform_score: float | None = None
    rationale: str | None = None
    scores: dict[str, Any] = Field(default_factory=dict)


class SceneAnalysisResult(BaseModel):
    """Returned by `analyze_video(...)`."""
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    intel_submodule_sha: str
    scenes: list[SceneRecord]
    raw_metrics: dict[str, Any] = Field(default_factory=dict)


class RankedClipCandidates(BaseModel):
    """Returned by `rank_clip_candidates(...)`."""
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    candidates: list[CandidateRecord]


class DirectorPlanRequest(BaseModel):
    """Input to `create_director_plan(...)`."""
    model_config = ConfigDict(extra="forbid")

    upload_id: str
    job_id: str
    platform_targets: list[PlatformTarget]
    ranked_candidates: RankedClipCandidates
    scenes: list[SceneRecord]
    tenant_plan: str = "creator"


AnalyzeVideoFn = Callable[[str, str], SceneAnalysisResult]
"""(upload_id, source_uri) -> SceneAnalysisResult"""

RankClipCandidatesFn = Callable[[str, list[SceneRecord]], RankedClipCandidates]
"""(upload_id, scenes) -> RankedClipCandidates"""

CreateDirectorPlanFn = Callable[[DirectorPlanRequest], DirectorPlan]
"""(request) -> DirectorPlan"""


class RenderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate: SelectedCandidate
    variant: Variant
    source_r2_key: str
    output_r2_prefix: str
    tenant_slug: str


RenderClipVariantFn = Callable[[str, RenderSettings], RenderResult]
"""(director_plan_id, render_settings) -> RenderResult"""


class IntelAdapter(Protocol):
    """Cluster of the four functions, for DI."""

    analyze_video: AnalyzeVideoFn
    rank_clip_candidates: RankClipCandidatesFn
    create_director_plan: CreateDirectorPlanFn
    render_clip_variant: RenderClipVariantFn
