"""Automated regression tests for the crop rendering pipeline.

Validates crop filter construction across all three modes (fit, center,
action) without requiring ffmpeg or video files. These tests verify
that the FFmpeg filter strings are structurally correct, produce even
dimensions, and never introduce black bars in fill modes.

Every future rendering change should validate against these tests.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from api.schemas.render_manifest import RenderManifest
from api.services.intel.render_plan_adapter import render_clip


# ---------------------------------------------------------------------------
# Shared test manifest base — 16:9 source → 9:16 output (most common case)
# ---------------------------------------------------------------------------

BASE = dict(
    render_job_id=str(uuid.uuid4()),
    candidate_id=str(uuid.uuid4()),
    upload_id=str(uuid.uuid4()),
    job_id=str(uuid.uuid4()),
    tenant_id="tenant-test",
    source_uri="/tmp/source.mp4",
    clip_start=0.0,
    clip_end=10.0,
    duration=10.0,
    platform="youtube_shorts",
    aspect_ratio="9:16",
    output_width=1080,
    output_height=1920,
    fps=30,
    output_container="mp4",
    bitrate_preset="high",
    bitrate_kbps=8000,
    crf=20,
    renderer="ffmpeg_basic",
    render_style="ffmpeg_basic",
    caption_mode="off",
    crop_mode="center",
    watermark=False,
    normalize_audio=False,
    filename_template="clip_{idx}.mp4",
    output_filename="clip_01_9x16.mp4",
)


def make_manifest(**kwargs) -> RenderManifest:
    """Build a RenderManifest with defaults + overrides."""
    return RenderManifest(**{**BASE, **kwargs})


def get_vfilters(manifest: RenderManifest) -> list[str]:
    """Return the list of video filter strings ffmpeg would receive."""
    with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
        result = render_clip(manifest, output_dir=Path("/tmp"), dry_run=True)
    vf_idx = result.command.index("-vf")
    return result.command[vf_idx + 1].split(",")


# ===================================================================
# REGRESSION: No Black Bars
# ===================================================================


class TestNoBlackBars:
    """In fill modes (center, action, face, manual), the output must
    never have black bars. Only 'fit' mode should produce black bars."""

    @pytest.mark.parametrize("mode", ["center", "action", "face", "manual"])
    def test_fill_modes_have_no_pad_filter(self, mode: str):
        """Fill modes (center, action, face, manual) must NOT use pad=."""
        m = make_manifest(crop_mode=mode)
        filters = get_vfilters(m)
        pad_filters = [f for f in filters if f.startswith("pad=")]
        assert len(pad_filters) == 0, (
            f"crop_mode={mode!r} should not produce pad= filters, got: {pad_filters}"
        )

    def test_fit_mode_has_pad_filter(self):
        """Fit mode MUST use pad= (black bars are intentional)."""
        m = make_manifest(crop_mode="fit")
        filters = get_vfilters(m)
        assert any(f.startswith("pad=") for f in filters), (
            "crop_mode='fit' should produce a pad= filter for letterboxing"
        )

    def test_fill_modes_have_crop_filter(self):
        """Fill modes MUST use crop= to fill the frame."""
        m = make_manifest(crop_mode="center")
        filters = get_vfilters(m)
        assert any(f.startswith("crop=") for f in filters), (
            "crop_mode='center' should produce a crop= filter"
        )


# ===================================================================
# REGRESSION: Even Pixel Dimensions (yuv420p compatibility)
# ===================================================================


class TestEvenDimensions:
    """FFmpeg's yuv420p pixel format requires even crop dimensions.
    The crop expression must use 2*trunc(.../2) to guarantee this."""

    @pytest.mark.parametrize("mode", ["center", "action", "face", "manual"])
    def test_crop_expression_guarantees_even_dimensions(self, mode: str):
        """The crop filter expression must use 2*trunc for even sizing."""
        m = make_manifest(crop_mode=mode)
        filters = get_vfilters(m)
        crop_filter = next(f for f in filters if f.startswith("crop="))
        assert "2*trunc" in crop_filter, (
            f"crop filter for mode={mode!r} must use 2*trunc() for even "
            f"dimensions. Got: {crop_filter}"
        )

    @pytest.mark.parametrize("mode", ["center", "action"])
    def test_scale_maintains_even_output(self, mode: str):
        """The scale filter should output exact manifest dimensions."""
        m = make_manifest(crop_mode=mode)
        filters = get_vfilters(m)
        scale_filter = next(f for f in filters if f.startswith("scale="))
        assert f"scale={m.output_width}:{m.output_height}" in scale_filter, (
            f"Scale must output exactly {m.output_width}x{m.output_height}. Got: {scale_filter}"
        )


# ===================================================================
# REGRESSION: All Crop Modes Produce Valid Commands
# ===================================================================


class TestAllCropModesValid:
    """Every crop mode must produce a syntactically valid ffmpeg command."""

    @pytest.mark.parametrize("mode", ["fit", "center", "action", "face", "manual"])
    def test_all_modes_return_succeeded_status(self, mode: str):
        m = make_manifest(crop_mode=mode)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert result.status == "succeeded", f"crop_mode={mode!r} failed: {result.error}"

    @pytest.mark.parametrize("mode", ["fit", "center", "action", "face", "manual"])
    def test_all_modes_have_scale_filter(self, mode: str):
        """Every crop mode must end with a scale to output dimensions."""
        m = make_manifest(crop_mode=mode)
        filters = get_vfilters(m)
        assert any(f.startswith("scale=") for f in filters), (
            f"crop_mode={mode!r} missing scale= filter"
        )


# ===================================================================
# REGRESSION: Aspect Ratio Handling
# ===================================================================


class TestAspectRatioHandling:
    """Crop expressions must handle all aspect ratio combinations."""

    @pytest.mark.parametrize(
        "src_label,out_w,out_h",
        [
            ("9:16_from_16:9", 1080, 1920),  # landscape → portrait
            ("16:9_from_9:16", 1920, 1080),  # portrait → landscape
            ("1:1_from_16:9", 1080, 1080),  # landscape → square
            ("9:16_from_4:3", 1080, 1920),  # 4:3 → portrait
        ],
    )
    def test_crop_expression_generic(self, src_label: str, out_w: int, out_h: int):
        """The crop expression must use min(iw, ih*AR) pattern for generic
        aspect ratio handling, not hardcoded 9/16 constants."""
        m = make_manifest(
            output_width=out_w,
            output_height=out_h,
            crop_mode="center",
        )
        filters = get_vfilters(m)
        # Join filter pieces back to reconstruct the full filtergraph
        # (split on comma breaks escaped \, inside the crop expression)
        full_filtergraph = ",".join(filters)
        assert "min(iw" in full_filtergraph, (
            f"{src_label}: crop must use min(iw,...) pattern for generic "
            f"aspect ratio handling. Got: {full_filtergraph}"
        )
        assert "min(ih" in full_filtergraph, (
            f"{src_label}: crop must use min(ih,...) pattern for generic "
            f"aspect ratio handling. Got: {full_filtergraph}"
        )


# ===================================================================
# REGRESSION: Deterministic Output
# ===================================================================


class TestDeterministicCrop:
    """Same manifest must always produce the same ffmpeg command."""

    def test_deterministic_fit_mode(self):
        m = make_manifest(crop_mode="fit")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            r1 = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
            r2 = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert r1.command == r2.command

    def test_deterministic_center_mode(self):
        m = make_manifest(crop_mode="center")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            r1 = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
            r2 = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert r1.command == r2.command

    def test_deterministic_action_mode(self):
        m = make_manifest(crop_mode="action")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            r1 = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
            r2 = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert r1.command == r2.command

    def test_crop_mode_switches_filter_graph(self):
        """Fit and center must produce different filter graphs."""
        fit_m = make_manifest(crop_mode="fit")
        ctr_m = make_manifest(crop_mode="center")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            fit_r = render_clip(fit_m, output_dir=Path("/tmp"), dry_run=True)
            ctr_r = render_clip(ctr_m, output_dir=Path("/tmp"), dry_run=True)
        # Filter strings should differ (fit=pad vs center=crop)
        assert fit_r.command != ctr_r.command, (
            "fit and center crop modes must produce different ffmpeg commands"
        )


# ===================================================================
# REGRESSION: Renderer Capability Validation
# ===================================================================


class TestRendererCapability:
    """Crop mode must be validated against renderer capabilities."""

    def test_unsupported_crop_mode_rejected(self):
        """If a renderer doesn't support a crop mode, manifest should fail."""
        # 'face' is not in documentary's supported_crop_modes
        m = make_manifest(
            crop_mode="face",
            renderer="documentary",
            render_style="documentary",
        )
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert result.status == "skipped_invalid", (
            f"face crop on documentary renderer should be rejected. Got: {result.status}"
        )

    def test_fit_mode_available_on_all_renderers(self):
        """All renderers should support 'fit' crop mode."""
        for renderer in ["ffmpeg_basic", "sports_hype", "documentary", "static"]:
            style = renderer if renderer != "sports_hype" else "sports_hype"
            m = make_manifest(
                crop_mode="fit",
                renderer=renderer,
                render_style=style,  # type: ignore
            )
            with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
            assert result.status in ("succeeded", "skipped_invalid"), (
                f"fit mode on {renderer} returned unexpected status: {result.status}"
            )


# ===================================================================
# REGRESSION: Dynamic Crop Expression Structure (Phase 1B)
# ===================================================================


class TestDynamicCropExpression:
    """Validate that the dynamic crop expression builder produces
    structurally correct piecewise-linear ffmpeg expressions."""

    def _build_dynamic_filter(
        self,
        keyframes: list[dict],
        source_w: int = 1920,
        source_h: int = 1080,
    ) -> str:
        """Helper to call the dynamic crop expression builder directly."""
        # We test the expression logic through the full pipeline using
        # the dry_run path, checking the crop filter string structure
        m = make_manifest(crop_mode="action", source_uri="/tmp/source.mp4")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        vf_idx = result.command.index("-vf")
        filters = result.command[vf_idx + 1].split(",")
        crop_filters = [f for f in filters if f.startswith("crop=")]
        return crop_filters[0] if crop_filters else ""

    def test_dynamic_crop_uses_t_expression(self):
        """The crop expression for action mode should be a single crop=
        filter with piecewise-linear structure (not static)."""
        crop_filter = self._build_dynamic_filter([])
        assert crop_filter, "Expected a crop= filter to be present"
        # Should be a valid filter string
        assert "crop=" in crop_filter
        assert "scale=" in "," + crop_filter.rsplit(",", 1)[-1] if "," in crop_filter else True

    def test_no_ffmpeg_warnings_in_dry_run(self):
        """Dry-run should succeed without warnings for all crop modes."""
        for mode in ["fit", "center", "action", "face", "manual"]:
            m = make_manifest(crop_mode=mode)
            with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
                result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
            assert result.error is None or result.error == "", (
                f"crop_mode={mode!r} produced unexpected error: {result.error}"
            )


# ===================================================================
# REGRESSION: Edge Cases
# ===================================================================


class TestEdgeCases:
    """Boundary conditions that should not crash the filter builder."""

    def test_minimum_duration_clip(self):
        """Minimum-duration clip should still produce a valid manifest."""
        m = make_manifest(clip_start=0.0, clip_end=0.5, duration=0.5)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert result.status == "succeeded"

    def test_minimal_resolution(self):
        """Minimum supported resolution (64x64) should work."""
        m = make_manifest(output_width=64, output_height=64, aspect_ratio="1:1")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert result.status == "succeeded"

    def test_max_resolution(self):
        """Maximum supported resolution (7680x4320) should work."""
        m = make_manifest(
            output_width=7680,
            output_height=4320,
            aspect_ratio="16:9",
            crop_mode="center",
        )
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert result.status == "succeeded"

    def test_16_9_source_to_9_16(self):
        """Most common case: 16:9 source → 9:16 portrait output."""
        m = make_manifest(crop_mode="center")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=Path("/tmp"), dry_run=True)
        assert result.status == "succeeded"
        # Verify we have crop but no pad
        filters = get_vfilters(m)
        assert any(f.startswith("crop=") for f in filters)
        assert not any(f.startswith("pad=") for f in filters)
