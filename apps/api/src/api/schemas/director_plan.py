"""Director Agent output contract.

This is the schema that holds the entire system together: the Director Agent
emits a `DirectorPlan` (one per job) that lists `SelectedCandidate` items.
Each candidate carries a list of `Variant`s — one per platform target.

The contract is the boundary between brain and renderers. Workers receive a
SelectedCandidate + Variant and resolve `render_style` into the concrete
renderer pipeline at dispatch time (see `intel.render_plan_adapter`).

Versioning: when this schema changes, bump `DIRECTOR_PLAN_VERSION` and write a
migration that backfills the version on existing rows.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DIRECTOR_PLAN_VERSION = "1"

PlatformTarget = Literal[
    "youtube_shorts",
    "tiktok",
    "instagram_reels",
    "x",
]

Pacing = Literal["fast", "medium", "slow"]
CaptionStyle = Literal["sports_hype", "minimal", "documentary"]
CropStrategy = Literal["center", "action", "face", "manual"]
RenderStyle = Literal[
    "ffmpeg_basic",
    "sports_hype",
    "documentary",
    "static",
]
AspectRatio = Literal["9:16", "1:1", "16:9"]


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: str
    platform: PlatformTarget
    aspect_ratio: AspectRatio
    duration_cap: int = Field(ge=1, le=600)
    caption_safe_zone: bool = True
    watermark: bool = True


class SelectedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    reason_selected: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    platform_score: float = Field(ge=0.0, le=1.0)
    clip_start: float = Field(ge=0.0)
    clip_end: float = Field(gt=0.0)
    duration: float = Field(gt=0.0)
    pacing: Pacing
    caption_style: CaptionStyle
    crop_strategy: CropStrategy
    render_style: RenderStyle
    hook_options: list[str] = Field(default_factory=list)
    variants: list[Variant]


class DirectorPlan(BaseModel):
    """The full plan for a single upload/job."""
    model_config = ConfigDict(extra="forbid")

    version: str = DIRECTOR_PLAN_VERSION
    upload_id: str
    job_id: str
    model: str
    prompt_version: str = "v1"
    platform_targets: list[PlatformTarget]
    selected_candidates: list[SelectedCandidate]
    cost_estimate_cents: int = Field(ge=0)


class RenderResult(BaseModel):
    """What a renderer worker writes back when finished."""
    model_config = ConfigDict(extra="forbid")

    variant_id: str
    candidate_id: str
    status: Literal["succeeded", "failed", "skipped"]
    r2_key: str | None = None
    duration_s: float | None = None
    bytes: int | None = None
    cost_cents: int = 0
    error: str | None = None
