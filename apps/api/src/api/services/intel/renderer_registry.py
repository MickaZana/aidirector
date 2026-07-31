"""Renderer capability registry.

Declares, in one place, what each renderer supports:
- aspect ratios
- render styles
- caption modes
- crop modes
- GPU requirements
- min/max clip duration
- explicit capability flags (watermark, normalize_audio, auto_crop)

Used at two points:
1. `render_manifest_builder` calls `validate_manifest` *before* persisting
   a RenderJob. Invalid combinations are rejected here, not at FFmpeg time.
2. `render_plan_adapter` calls `get_renderer` to look up dispatch info.

Adding a new renderer requires only an entry below. Code paths in the
adapter dispatch on `RendererCapability.renderer` so the new renderer is
addressable as soon as it's registered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from api.schemas.director_plan import AspectRatio, CropStrategy, RenderStyle
from api.schemas.render_manifest import CaptionMode, Renderer, RenderManifest


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    reasons: tuple[str, ...] = ()

    @classmethod
    def ok(cls) -> "CompatibilityResult":
        return cls(compatible=True, reasons=())

    @classmethod
    def fail(cls, *reasons: str) -> "CompatibilityResult":
        return cls(compatible=False, reasons=tuple(reasons))


@dataclass(frozen=True)
class RendererCapability:
    """One row of the registry."""

    renderer: Renderer
    supported_aspect_ratios: frozenset[AspectRatio]
    supported_styles: frozenset[RenderStyle]
    supported_caption_modes: frozenset[CaptionMode]
    supported_crop_modes: frozenset[CropStrategy]
    gpu_required: bool
    capabilities: frozenset[str]
    min_duration_s: float
    max_duration_s: float
    notes: str = ""


# --- Registry contents ------------------------------------------------------
# Adding a new renderer: append to RENDERERS, then add the dispatch branch
# in render_plan_adapter. The probe will assert the registry is consistent
# with the dispatch table.

_FFMPEG_BASIC = RendererCapability(
    renderer="ffmpeg_basic",
    supported_aspect_ratios=frozenset({"9:16", "1:1", "16:9"}),
    supported_styles=frozenset({"ffmpeg_basic", "sports_hype", "documentary"}),
    supported_caption_modes=frozenset({"off", "basic"}),
    supported_crop_modes=frozenset({"fit", "center", "action", "face", "manual"}),
    gpu_required=False,
    capabilities=frozenset({"watermark", "normalize_audio", "scale", "pad", "crop"}),
    min_duration_s=0.5,
    max_duration_s=600.0,
    notes="Baseline CPU FFmpeg pipeline. Phase 5 default.",
)

_SPORTS_HYPE = RendererCapability(
    renderer="sports_hype",
    supported_aspect_ratios=frozenset({"9:16", "1:1"}),
    supported_styles=frozenset({"sports_hype"}),
    supported_caption_modes=frozenset({"basic", "sports_hype"}),
    supported_crop_modes=frozenset({"fit", "center", "action"}),
    gpu_required=False,
    capabilities=frozenset(
        {"watermark", "normalize_audio", "scale", "pad", "crop", "kinetic_captions"}
    ),
    min_duration_s=3.0,
    max_duration_s=120.0,
    notes="Phase 5 stub. Falls back to ffmpeg_basic execution path until kinetic-caption "
    "renderer ships.",
)

_DOCUMENTARY = RendererCapability(
    renderer="documentary",
    supported_aspect_ratios=frozenset({"16:9", "1:1"}),
    supported_styles=frozenset({"documentary"}),
    supported_caption_modes=frozenset({"off", "basic", "documentary"}),
    supported_crop_modes=frozenset({"fit", "center"}),
    gpu_required=False,
    capabilities=frozenset(
        {"watermark", "normalize_audio", "scale", "pad", "crop", "lower_thirds"}
    ),
    min_duration_s=5.0,
    max_duration_s=600.0,
    notes="Phase 5 stub. Documentary renderer is for landscape and square output.",
)

_STATIC = RendererCapability(
    renderer="static",
    supported_aspect_ratios=frozenset({"9:16", "1:1", "16:9"}),
    supported_styles=frozenset({"static"}),
    supported_caption_modes=frozenset({"off"}),
    supported_crop_modes=frozenset({"fit", "center"}),
    gpu_required=False,
    capabilities=frozenset({"watermark", "crop", "static_template"}),
    min_duration_s=1.0,
    max_duration_s=15.0,
    notes="Static-image renderer. Caller supplies template + duration.",
)

_CONVERSATION = RendererCapability(
    renderer="conversation",
    supported_aspect_ratios=frozenset({"9:16", "16:9", "1:1"}),
    supported_styles=frozenset({"conversation"}),
    supported_caption_modes=frozenset({"basic", "documentary"}),
    supported_crop_modes=frozenset({"fit", "center", "face", "smart"}),
    gpu_required=False,
    capabilities=frozenset({"watermark", "scale", "pad", "crop"}),
    min_duration_s=3.0,
    max_duration_s=600.0,
    notes="Conversation renderer with speaker-aware crop contract and speech-preserving audio.",
)


RENDERERS: dict[Renderer, RendererCapability] = {
    _FFMPEG_BASIC.renderer: _FFMPEG_BASIC,
    _SPORTS_HYPE.renderer: _SPORTS_HYPE,
    _DOCUMENTARY.renderer: _DOCUMENTARY,
    _STATIC.renderer: _STATIC,
    _CONVERSATION.renderer: _CONVERSATION,
}


# --- API --------------------------------------------------------------------


def get_renderer(renderer: Renderer) -> RendererCapability:
    if renderer not in RENDERERS:
        raise KeyError(f"Unknown renderer: {renderer!r}")
    return RENDERERS[renderer]


def list_renderers() -> Iterable[RendererCapability]:
    return RENDERERS.values()


def renderer_for_style(style: RenderStyle) -> Renderer:
    """Map an editorial render_style to the concrete renderer that handles it.

    Deterministic and total: every RenderStyle in the DirectorPlan contract
    maps to exactly one renderer in the registry. If a future style is added
    without a matching renderer, the builder will get a KeyError here — a
    loud, debuggable failure rather than a silent FFmpeg explosion.
    """
    # Prefer the renderer whose identity matches the editorial style. The
    # baseline renderer advertises compatibility fallbacks, but must not
    # swallow dedicated Podcast/documentary output.
    if style in RENDERERS:
        return style  # type: ignore[return-value]
    for cap in RENDERERS.values():
        if style in cap.supported_styles:
            return cap.renderer
    raise KeyError(f"No renderer supports style: {style!r}")


def validate_manifest(manifest: RenderManifest) -> CompatibilityResult:
    """Check whether a manifest is renderable.

    Returns OK or a list of reasons. Callers (the builder, the worker)
    decide what to do with failures — reject, fall back, or surface to the
    operator. Either way, FFmpeg never runs against an invalid manifest.
    """
    cap = RENDERERS.get(manifest.renderer)
    if cap is None:
        return CompatibilityResult.fail(f"unknown renderer: {manifest.renderer!r}")

    reasons: list[str] = []

    if manifest.aspect_ratio not in cap.supported_aspect_ratios:
        reasons.append(
            f"aspect {manifest.aspect_ratio!r} not in {sorted(cap.supported_aspect_ratios)}"
        )
    if manifest.render_style not in cap.supported_styles:
        reasons.append(
            f"render_style {manifest.render_style!r} not in {sorted(cap.supported_styles)}"
        )
    if manifest.caption_mode not in cap.supported_caption_modes:
        reasons.append(
            f"caption_mode {manifest.caption_mode!r} not in {sorted(cap.supported_caption_modes)}"
        )
    if manifest.crop_mode not in cap.supported_crop_modes:
        reasons.append(
            f"crop_mode {manifest.crop_mode!r} not in {sorted(cap.supported_crop_modes)}"
        )
    if manifest.duration < cap.min_duration_s:
        reasons.append(f"duration {manifest.duration} < min_duration_s {cap.min_duration_s}")
    if manifest.duration > cap.max_duration_s:
        reasons.append(f"duration {manifest.duration} > max_duration_s {cap.max_duration_s}")
    if manifest.watermark and "watermark" not in cap.capabilities:
        reasons.append(f"renderer {manifest.renderer!r} lacks watermark capability")
    if manifest.normalize_audio and "normalize_audio" not in cap.capabilities:
        reasons.append(f"renderer {manifest.renderer!r} lacks normalize_audio capability")

    if reasons:
        return CompatibilityResult.fail(*reasons)
    return CompatibilityResult.ok()
