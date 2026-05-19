"""RenderManifest — the executable render contract.

DirectorPlan is editorial intent. RenderManifest is what the renderer
actually executes. The two **must not** be the same object.

A RenderManifest is built by `services/render_manifest_builder` from a
DirectorPlan + per-platform constraints + renderer compatibility. It is
the only object the FFmpeg/OmegaClips execution layer ever reads. This
boundary means:

1. DirectorPlan changes (new pacing labels, new render_style enums) do
   not silently change FFmpeg commands.
2. RenderManifest fields are exact and execution-safe — no derived,
   editorial, or human-readable fields leak past the builder.
3. The renderer never reads DirectorPlan JSON. If it needs a new knob, the
   knob is added here first and the builder is updated.

Versioning: bump `RENDER_MANIFEST_VERSION` when this schema changes;
backfill via migration.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.director_plan import (
    AspectRatio,
    CaptionStyle,
    CropStrategy,
    PlatformTarget,
    RenderStyle,
)

RENDER_MANIFEST_VERSION = "1"

Renderer = Literal[
    "ffmpeg_basic",
    "sports_hype",
    "documentary",
    "static",
]
"""Concrete render pipeline that consumes this manifest.

Distinct from `render_style` (editorial label from DirectorPlan) — the
builder maps style → renderer based on renderer_registry rules. Adding a
new renderer requires:
  1. Adding the literal here
  2. Adding a `RendererCapability` entry in renderer_registry
  3. Adding a dispatch branch in render_plan_adapter
"""

CaptionMode = Literal["off", "basic", "sports_hype", "documentary"]

BitratePreset = Literal["low", "medium", "high"]

OutputContainer = Literal["mp4", "mov", "webm"]


class RenderManifest(BaseModel):
    """The executable render contract. Validated on construction."""

    model_config = ConfigDict(extra="forbid")

    version: str = RENDER_MANIFEST_VERSION
    render_job_id: str
    candidate_id: str
    upload_id: str
    job_id: str
    tenant_id: str

    # --- source slicing -------------------------------------------------
    source_uri: str
    clip_start: Annotated[float, Field(ge=0.0)]
    clip_end: Annotated[float, Field(gt=0.0)]
    duration: Annotated[float, Field(gt=0.0)]

    # --- output geometry ------------------------------------------------
    platform: PlatformTarget
    aspect_ratio: AspectRatio
    output_width: Annotated[int, Field(ge=64, le=7680)]
    output_height: Annotated[int, Field(ge=64, le=7680)]
    fps: Annotated[int, Field(ge=1, le=120)] = 30
    output_container: OutputContainer = "mp4"

    # --- encoding -------------------------------------------------------
    bitrate_preset: BitratePreset
    bitrate_kbps: Annotated[int, Field(ge=200, le=50000)]
    crf: Annotated[int, Field(ge=0, le=51)] = 23

    # --- creative + execution knobs ------------------------------------
    renderer: Renderer
    render_style: RenderStyle
    caption_mode: CaptionMode
    crop_mode: CropStrategy
    watermark: bool = True
    normalize_audio: bool = True

    # --- artifact naming -----------------------------------------------
    filename_template: str
    output_filename: str

    # --- execution-time metadata (carries through to RenderOutput) -----
    execution_metadata: dict = Field(default_factory=dict)
