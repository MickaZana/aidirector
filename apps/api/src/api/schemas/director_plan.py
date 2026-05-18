"""Director Agent output contract.

This is the schema that holds the entire system together: the Director Agent
emits a `DirectorPlan` (one per job) that lists `SceneDecision` items. Each
decision names exactly one pipeline and carries its typed parameters. The
orchestrator dispatches each decision to the named pipeline's queue.

OmegaClips' claude_intelligence.generate_segment_render_plan() returns
dict-shaped data today; the Director Agent worker validates its output against
this schema before persisting and dispatching. Schema breaks are caught here,
not at render time.

Versioning: when this schema changes, bump `DIRECTOR_PLAN_VERSION` and write a
migration that backfills the version field on existing rows.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

DIRECTOR_PLAN_VERSION = "1"


class _PipelineParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FFmpegFinisherParams(_PipelineParams):
    pipeline: Literal["ffmpeg_finisher"] = "ffmpeg_finisher"
    target_aspect: Literal["9:16", "1:1", "16:9"] = "9:16"
    target_duration_s: float = Field(ge=3.0, le=180.0)
    speed_multiplier: float = Field(default=1.0, ge=0.25, le=4.0)
    loudness_lufs: float = Field(default=-14.0, ge=-23.0, le=-9.0)


class CaptionEngineParams(_PipelineParams):
    pipeline: Literal["caption_engine"] = "caption_engine"
    preset: str = "modern_bold"
    emphasize_keywords: list[str] = Field(default_factory=list)
    language: str = "en"


class AutoCropParams(_PipelineParams):
    pipeline: Literal["auto_crop"] = "auto_crop"
    target_aspect: Literal["9:16", "1:1", "16:9"] = "9:16"
    subject_lock: bool = True


class StaticGeneratorParams(_PipelineParams):
    pipeline: Literal["static_generator"] = "static_generator"
    template: Literal["quote_card", "stat_overlay", "score_graphic", "thumbnail"]
    duration_s: float = Field(default=4.0, ge=1.0, le=15.0)
    text: dict[str, str] = Field(default_factory=dict)


class HyperFramesParams(_PipelineParams):
    pipeline: Literal["hyperframes"] = "hyperframes"
    interpolation: Literal["none", "rife", "film"] = "rife"
    target_fps: int = Field(default=60, ge=24, le=120)
    impact_zooms: bool = True
    kinetic_text: bool = True


class RemotionParams(_PipelineParams):
    pipeline: Literal["remotion"] = "remotion"
    template_id: str
    props: dict[str, str | int | float | bool] = Field(default_factory=dict)


PipelineParams = Annotated[
    Union[
        FFmpegFinisherParams,
        CaptionEngineParams,
        AutoCropParams,
        StaticGeneratorParams,
        HyperFramesParams,
        RemotionParams,
    ],
    Field(discriminator="pipeline"),
]


class SceneDecision(BaseModel):
    """One renderable decision the Director Agent committed to."""
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    t_start: float = Field(ge=0.0)
    t_end: float = Field(gt=0.0)
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    params: PipelineParams


class DirectorPlan(BaseModel):
    """The full plan for a single job."""
    model_config = ConfigDict(extra="forbid")

    version: str = DIRECTOR_PLAN_VERSION
    job_id: str
    prompt_version: str
    model: str
    decisions: list[SceneDecision]
    cost_estimate_cents: int = Field(ge=0)


class RenderResult(BaseModel):
    """What a renderer worker writes back when finished."""
    model_config = ConfigDict(extra="forbid")

    scene_id: str
    pipeline: str
    status: Literal["succeeded", "failed", "skipped"]
    r2_key: str | None = None
    duration_s: float | None = None
    cost_cents: int = 0
    error: str | None = None
