"""Render Plan Adapter — the single execution boundary.

Consumes a validated `RenderManifest`. Never reads DirectorPlan JSON
directly. Never accepts arbitrary kwargs. The renderer choice is fixed by
the manifest; this adapter only dispatches to the right execution path
and shells out to FFmpeg.

Phase 5 implementation:
- `ffmpeg_basic`, `sports_hype`, `documentary` → real FFmpeg subprocess.
  The renderer-specific filter graphs differ in caption/colour treatment
  but all share the same cut/scale/pad/encode skeleton.
- `static` → not wired in Phase 5 (would generate a static image-as-video
  via FFmpeg's `-loop 1 -i image -t duration`). Raises NotImplementedError.

The adapter is process-local: it shells out to `ffmpeg` on PATH. The Modal
worker image already has ffmpeg installed (see `workers/modal_app.py::intel_image`).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

log = logging.getLogger(__name__)

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.render_manifest import RenderManifest
from api.services.intel.renderer_registry import get_renderer, validate_manifest


class RenderExecutionResult(BaseModel):
    """What the adapter returns for a single manifest execution."""

    model_config = ConfigDict(extra="forbid")

    render_job_id: str
    candidate_id: str
    status: str  # "succeeded" | "failed" | "skipped_invalid"
    output_path: str | None = None
    bytes: int | None = None
    duration_s: float | None = None
    renderer: str
    command: list[str] = Field(default_factory=list)
    stderr_tail: str | None = None
    elapsed_seconds: float = 0.0
    error: str | None = None


def render_clip(
    manifest: RenderManifest,
    *,
    output_dir: Path,
    ffmpeg_bin: str | None = None,
    timeout_s: float = 120.0,
    dry_run: bool = False,
) -> RenderExecutionResult:
    """Render one variant defined by a validated `RenderManifest`.

    Validation: the manifest is re-checked against the renderer registry
    here. The render layer is defensive — even if the builder slipped a
    bad manifest through, this gate catches it.

    `dry_run=True` produces the FFmpeg command list and a `skipped_invalid`-
    or-`succeeded`-style result without executing. Used by the probe to
    prove command construction is deterministic.

    `ffmpeg_bin` overrides the binary lookup (useful when the binary lives
    outside PATH, e.g. winget-installed ffmpeg on Windows).
    """
    compat = validate_manifest(manifest)
    if not compat.compatible:
        return RenderExecutionResult(
            render_job_id=manifest.render_job_id,
            candidate_id=manifest.candidate_id,
            status="skipped_invalid",
            renderer=manifest.renderer,
            command=[],
            error="; ".join(compat.reasons),
            elapsed_seconds=0.0,
        )

    ffmpeg = ffmpeg_bin or shutil.which("ffmpeg")
    if not ffmpeg:
        return RenderExecutionResult(
            render_job_id=manifest.render_job_id,
            candidate_id=manifest.candidate_id,
            status="failed",
            renderer=manifest.renderer,
            command=[],
            error="ffmpeg binary not found on PATH; pass ffmpeg_bin explicitly",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / manifest.output_filename

    args = _build_ffmpeg_command(ffmpeg, manifest, output_path)

    if dry_run:
        return RenderExecutionResult(
            render_job_id=manifest.render_job_id,
            candidate_id=manifest.candidate_id,
            status="succeeded",  # command construction succeeded
            renderer=manifest.renderer,
            command=args,
            output_path=str(output_path),
            duration_s=manifest.duration,
            elapsed_seconds=0.0,
        )

    log.info(
        "render_clip: start candidate=%s renderer=%s platform=%s duration=%.1fs",
        manifest.candidate_id,
        manifest.renderer,
        manifest.platform,
        manifest.duration,
    )
    started = time.monotonic()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        log.error(
            "render_clip: ffmpeg timed out candidate=%s timeout=%.1fs elapsed=%.1fs",
            manifest.candidate_id,
            timeout_s,
            elapsed,
        )
        return RenderExecutionResult(
            render_job_id=manifest.render_job_id,
            candidate_id=manifest.candidate_id,
            status="failed",
            renderer=manifest.renderer,
            command=args,
            stderr_tail=(exc.stderr.decode() if exc.stderr else "")[-500:],
            elapsed_seconds=elapsed,
            error=f"ffmpeg timed out after {timeout_s}s",
        )
    elapsed = time.monotonic() - started

    if proc.returncode != 0:
        log.error(
            "render_clip: ffmpeg failed candidate=%s rc=%d elapsed=%.1fs stderr=%s",
            manifest.candidate_id,
            proc.returncode,
            elapsed,
            (proc.stderr or "")[-200:],
        )
        return RenderExecutionResult(
            render_job_id=manifest.render_job_id,
            candidate_id=manifest.candidate_id,
            status="failed",
            renderer=manifest.renderer,
            command=args,
            stderr_tail=(proc.stderr or "").splitlines()[-12:].__str__(),
            elapsed_seconds=elapsed,
            error=f"ffmpeg exit {proc.returncode}",
        )

    try:
        size_bytes = output_path.stat().st_size if output_path.exists() else None
    except OSError:
        size_bytes = None

    log.info(
        "render_clip: succeeded candidate=%s elapsed=%.1fs bytes=%s",
        manifest.candidate_id,
        elapsed,
        size_bytes,
    )
    return RenderExecutionResult(
        render_job_id=manifest.render_job_id,
        candidate_id=manifest.candidate_id,
        status="succeeded",
        output_path=str(output_path),
        bytes=size_bytes,
        duration_s=manifest.duration,
        renderer=manifest.renderer,
        command=args,
        elapsed_seconds=elapsed,
    )


# --- Internals --------------------------------------------------------------


def _find_drawtext_font() -> str | None:
    """Return a path to a TTF the drawtext filter can use, or None.

    Resolution order:
      1. FFMPEG_DRAWTEXT_FONT env var — absolute path set by the operator.
      2. Well-known system paths probed at startup (Windows, macOS, Linux).
      3. None — drawtext picks its built-in default (safe for ASCII titles).

    A warning is emitted when no font resolves so ops can act on it rather
    than discovering the issue via tofu boxes in rendered clips.
    """
    import os

    override = os.environ.get("FFMPEG_DRAWTEXT_FONT", "").strip()
    if override:
        if os.path.exists(override):
            return override
        log.warning(
            "_find_drawtext_font: FFMPEG_DRAWTEXT_FONT=%r not found, falling back", override
        )

    candidates = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    log.warning(
        "_find_drawtext_font: no font found on this system; title burn-in will use "
        "ffmpeg default (may produce tofu for non-ASCII). Set FFMPEG_DRAWTEXT_FONT "
        "to an absolute .ttf path to silence this."
    )
    return None


# Module-level cache — resolved once per process.
_DRAWTEXT_FONT = _find_drawtext_font()


def _drawtext_escape(s: str) -> str:
    """Escape a string for ffmpeg drawtext's text= argument.

    drawtext is parsed twice (once as a filter arg, once as drawtext's own
    quoted-text), so the safe characters list is small. We keep ASCII
    printable, replace single quotes (which would terminate the text=),
    backslashes, colons (filter separator), and percent (drawtext format spec).
    """
    return (
        s.replace("\\", "\\\\")
        .replace("'", "’")  # curly apostrophe — safe inside text=
        .replace(":", r"\:")
        .replace("%", r"\%")
    )


def _subtitles_filter_path(p: str) -> str:
    """Encode a subtitle file path for ffmpeg's `subtitles=` filter.

    Windows paths cause two specific problems for the subtitles filter:
    1. Backslashes get consumed by ffmpeg's filter parser.
    2. The drive-letter colon (`C:`) is read as a filter argument separator.

    Solution: forward-slash the path and escape the colon. Wrapping in
    single quotes is *not* enough on Windows — the colon escape is required.
    """
    forward = p.replace("\\", "/")
    return forward.replace(":", r"\:")


def _build_ffmpeg_command(ffmpeg: str, manifest: RenderManifest, output_path: Path) -> list[str]:
    """Deterministic FFmpeg command. Same manifest → same command bytes."""
    cap = get_renderer(manifest.renderer)
    has_normalize = manifest.normalize_audio and "normalize_audio" in cap.capabilities
    has_watermark = manifest.watermark and "watermark" in cap.capabilities

    vfilters = [
        f"scale={manifest.output_width}:{manifest.output_height}"
        f":force_original_aspect_ratio=decrease",
        f"pad={manifest.output_width}:{manifest.output_height}:(ow-iw)/2:(oh-ih)/2:black",
    ]

    # Title banner: top-center, white text with semi-opaque black box for
    # readability against any underlying frame.
    #
    # drawtext doesn't auto-wrap, so we size the font to make the title fit
    # within the output width regardless of length AND aspect ratio:
    #   - height cap: ~4% of frame height (so it doesn't dwarf a 16:9
    #     wide-but-short frame).
    #   - width-fit: enough headroom to fit `len(title)` chars in
    #     output_width minus side padding, assuming an Arial-like proportional
    #     font where avg char width ≈ 0.55 × font size.
    # The smaller of those two wins, clamped to a 20px floor for legibility.
    if manifest.title:
        title_text = manifest.title
        side_padding_px = 80
        char_ratio = 0.55
        char_count = max(8, len(title_text))
        width_fit = int((manifest.output_width - side_padding_px) / (char_count * char_ratio))
        height_cap = max(28, manifest.output_height // 24)
        title_font_size = max(20, min(width_fit, height_cap))
        # boxborderw scaled to the chosen font so the box never looks bolted on.
        box_pad = max(8, title_font_size // 5)
        # drawtext fontfile= path needs the drive-letter colon escaped at
        # BOTH parser levels — the filter-graph parser (level 1) AND the
        # drawtext arg parser (level 2). Wrapping the value in single quotes
        # only handles level 1; we additionally backslash-escape so drawtext
        # itself doesn't split on the colon.
        fontfile_arg = f"fontfile='{_DRAWTEXT_FONT.replace(':', r'\:')}':" if _DRAWTEXT_FONT else ""
        vfilters.append(
            f"drawtext={fontfile_arg}text='{_drawtext_escape(title_text)}':"
            f"fontcolor=white:fontsize={title_font_size}:"
            f"box=1:boxcolor=black@0.55:boxborderw={box_pad}:"
            f"x=(w-text_w)/2:y=h*0.04"
        )

    # Subtitles burn-in: drives off an SRT file, full styling inline so a
    # font is always picked (Windows ffmpeg without a config doesn't have a
    # default Sans on PATH).
    #
    # libass treats SRT input as living on a 384x288 virtual canvas
    # (ffmpeg's default PlayResX/Y for SRT-loaded subs). FontSize and
    # MarginV are in those virtual units, scaled to the real output frame
    # at render time. So for any output resolution we use the same
    # proportional numbers (font ~5% of frame height, bottom margin
    # ~8% of frame height).
    if manifest.subtitle_uri:
        force_style = (
            "FontName=Arial,"
            "FontSize=16,"  # ~5% of frame height (libass scales)
            "PrimaryColour=&H00FFFFFF,"  # white
            "OutlineColour=&H00000000,"  # black outline
            "BorderStyle=1,"  # outline + drop shadow
            "Outline=2,"
            "Shadow=1,"
            "Bold=-1,"
            "Alignment=2,"  # bottom-center
            "MarginV=24"  # ~8% of frame height
        )
        vfilters.append(
            f"subtitles='{_subtitles_filter_path(manifest.subtitle_uri)}'"
            f":force_style='{force_style}'"
        )

    if has_watermark:
        # Tiny corner watermark; deterministic content + position.
        vfilters.append(
            "drawtext=text='aidirector':fontcolor=white@0.6:fontsize=14:x=w-tw-10:y=h-th-10"
        )

    afilters: list[str] = []
    if has_normalize:
        # FFmpeg's single-pass loudnorm; deterministic enough for fixtures.
        afilters.append("loudnorm=I=-14:LRA=11:TP=-1.5")

    args: list[str] = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{manifest.clip_start:.3f}",
        "-i",
        manifest.source_uri,
        "-t",
        f"{manifest.duration:.3f}",
        "-r",
        str(manifest.fps),
        "-vf",
        ",".join(vfilters),
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        str(manifest.crf),
        "-b:v",
        f"{manifest.bitrate_kbps}k",
        "-pix_fmt",
        "yuv420p",
    ]

    if afilters:
        args += ["-af", ",".join(afilters), "-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]

    args.append(str(output_path))
    return args
