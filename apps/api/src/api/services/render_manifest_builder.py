"""Build RenderManifest objects from a DirectorPlan.

The single conversion point: editorial intent (DirectorPlan) → executable
intent (RenderManifest). Every cross-cutting concern that needs to land
on the FFmpeg side gets translated here:

  - aspect_ratio + platform_optimizer preset → output_width × output_height
  - render_style + renderer_registry → renderer dispatch slot
  - caption_style → caption_mode (downcast for safety)
  - filename template → fully-rendered output filename
  - safety thresholds → min/max duration enforcement via the registry

Outputs are individually validated against the renderer registry; invalid
manifests are excluded (with reasons in `unrenderable`) rather than thrown,
so a partial plan can still ship the renderable variants.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from api.schemas.director_plan import (
    CaptionStyle,
    DirectorPlan,
    PlatformTarget,
    SelectedCandidate,
    Variant,
)
from api.schemas.render_manifest import (
    BitratePreset,
    CaptionMode,
    RenderManifest,
)
from api.services.intel.renderer_registry import (
    CompatibilityResult,
    get_renderer,
    renderer_for_style,
    validate_manifest,
)
from api.services.platform_optimizer import filename_for, get_preset


@dataclass(frozen=True)
class ManifestBuildResult:
    manifests: tuple[RenderManifest, ...]
    unrenderable: tuple[tuple[str, str, CompatibilityResult], ...]
    """Triples of (candidate_id, variant_id, reason) for excluded combos."""


def build_manifests(
    *,
    plan: DirectorPlan,
    source_uri: str,
    tenant_id: str,
    tenant_slug: str,
) -> ManifestBuildResult:
    """Convert all variants in a DirectorPlan into RenderManifest objects.

    Variants that fail renderer-compatibility validation are excluded with
    a recorded reason. The caller decides whether to surface, retry, or
    fail the whole batch.
    """
    manifests: list[RenderManifest] = []
    unrenderable: list[tuple[str, str, CompatibilityResult]] = []

    for candidate in plan.selected_candidates:
        for variant in candidate.variants:
            manifest = _build_one(
                plan=plan,
                candidate=candidate,
                variant=variant,
                source_uri=source_uri,
                tenant_id=tenant_id,
                tenant_slug=tenant_slug,
            )
            result = validate_manifest(manifest)
            if not result.compatible:
                unrenderable.append((candidate.candidate_id, variant.variant_id, result))
                continue
            manifests.append(manifest)

    return ManifestBuildResult(
        manifests=tuple(manifests), unrenderable=tuple(unrenderable)
    )


# --- Internals --------------------------------------------------------------


def _build_one(
    *,
    plan: DirectorPlan,
    candidate: SelectedCandidate,
    variant: Variant,
    source_uri: str,
    tenant_id: str,
    tenant_slug: str,
) -> RenderManifest:
    preset = get_preset(variant.platform)
    width, height = preset["resolution"]

    # Cap clip duration to the platform duration cap; the editorial clip
    # duration may exceed the platform cap for some variants.
    duration = min(float(candidate.duration), float(variant.duration_cap))
    clip_end = candidate.clip_start + duration

    renderer = renderer_for_style(candidate.render_style)
    cap = get_renderer(renderer)
    bitrate_preset = _bitrate_preset_for_platform(variant.platform)
    bitrate_kbps = int(preset["bitrate_kbps"])
    crf = int(preset["crf"])
    caption_mode = _caption_mode_for_style(candidate.caption_style, renderer)
    crop_mode = _crop_mode_for_renderer(candidate.crop_strategy, renderer)
    watermark = variant.watermark and "watermark" in cap.capabilities
    normalize_audio = "normalize_audio" in cap.capabilities
    filename = filename_for(variant.platform, tenant_slug, candidate.candidate_id)

    return RenderManifest(
        render_job_id=str(uuid.uuid4()),
        candidate_id=candidate.candidate_id,
        upload_id=plan.upload_id,
        job_id=plan.job_id,
        tenant_id=tenant_id,
        source_uri=source_uri,
        clip_start=float(candidate.clip_start),
        clip_end=clip_end,
        duration=duration,
        platform=variant.platform,
        aspect_ratio=variant.aspect_ratio,
        output_width=int(width),
        output_height=int(height),
        fps=30,
        output_container="mp4",
        bitrate_preset=bitrate_preset,
        bitrate_kbps=bitrate_kbps,
        crf=crf,
        renderer=renderer,
        render_style=candidate.render_style,
        caption_mode=caption_mode,
        crop_mode=crop_mode,
        watermark=watermark,
        normalize_audio=normalize_audio,
        filename_template=preset["filename_template"],
        output_filename=filename,
        execution_metadata={
            "pacing": candidate.pacing,
            "hook_options": list(candidate.hook_options),
            "caption_safe_zone": variant.caption_safe_zone,
            "platform": variant.platform,
            "platform_preset": dict(preset),
        },
    )


def _bitrate_preset_for_platform(platform: PlatformTarget) -> BitratePreset:
    # Cheap mapping for now; real ML/heuristic tuning lands later.
    if platform in ("youtube_shorts",):
        return "high"
    if platform in ("tiktok", "instagram_reels"):
        return "medium"
    return "medium"


def _caption_mode_for_style(style: CaptionStyle, renderer: str) -> CaptionMode:
    """Downcast editorial caption_style to a renderer-supported caption_mode.

    If the renderer supports the editorial mode, use it. Otherwise fall back
    in this order: basic → off. The registry is the source of truth; this
    function never invents an unsupported mode.
    """
    cap = get_renderer(renderer)  # type: ignore[arg-type]
    desired: CaptionMode
    if style == "sports_hype":
        desired = "sports_hype"
    elif style == "documentary":
        desired = "documentary"
    else:
        desired = "basic"
    if desired in cap.supported_caption_modes:
        return desired
    for fallback in ("basic", "off"):
        if fallback in cap.supported_caption_modes:
            return fallback  # type: ignore[return-value]
    return "off"


def _crop_mode_for_renderer(crop_mode, renderer):  # noqa: ANN001
    """Downcast crop_mode to renderer-supported. Falls back to center."""
    cap = get_renderer(renderer)
    if crop_mode in cap.supported_crop_modes:
        return crop_mode
    if "center" in cap.supported_crop_modes:
        return "center"
    return next(iter(cap.supported_crop_modes))
