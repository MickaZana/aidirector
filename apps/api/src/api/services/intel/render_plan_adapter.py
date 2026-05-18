"""Adapter: maps Director Plan render_style -> OmegaClips pipeline call.

The Director Agent emits high-level `render_style` enums
(`ffmpeg_basic`, `sports_hype`, `documentary`, `static`). This adapter
translates each to the concrete OmegaClips renderer pipeline + params.
"""
from __future__ import annotations

from typing import TypedDict

from api.schemas.director_plan import RenderStyle, SelectedCandidate, Variant
from api.services.platform_optimizer import get_preset


class ResolvedRenderSpec(TypedDict):
    """What the renderer worker actually executes."""

    pipeline: str
    target_aspect: str
    target_duration_s: float
    crf: int
    bitrate_kbps: int
    resolution: tuple[int, int]
    watermark: bool
    caption_preset: str | None
    crop_strategy: str
    extra: dict[str, object]


_RENDER_STYLE_TO_PIPELINE: dict[RenderStyle, str] = {
    "ffmpeg_basic": "ffmpeg_finisher",
    "sports_hype": "ffmpeg_finisher",
    "documentary": "ffmpeg_finisher",
    "static": "static_generator",
}


_RENDER_STYLE_TO_CAPTION_PRESET: dict[RenderStyle, str | None] = {
    "ffmpeg_basic": "modern_bold",
    "sports_hype": "kinetic_sports",
    "documentary": "subtle_serif",
    "static": None,
}


def resolve_render_spec(
    candidate: SelectedCandidate, variant: Variant
) -> ResolvedRenderSpec:
    preset = get_preset(variant.platform)
    pipeline = _RENDER_STYLE_TO_PIPELINE[candidate.render_style]
    caption_preset = _RENDER_STYLE_TO_CAPTION_PRESET[candidate.render_style]

    duration = min(candidate.duration, float(variant.duration_cap))

    return {
        "pipeline": pipeline,
        "target_aspect": variant.aspect_ratio,
        "target_duration_s": duration,
        "crf": preset["crf"],
        "bitrate_kbps": preset["bitrate_kbps"],
        "resolution": preset["resolution"],
        "watermark": variant.watermark,
        "caption_preset": caption_preset,
        "crop_strategy": candidate.crop_strategy,
        "extra": {
            "pacing": candidate.pacing,
            "hook_options": candidate.hook_options,
            "caption_safe_zone": variant.caption_safe_zone,
        },
    }
