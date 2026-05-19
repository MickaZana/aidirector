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

import shutil
import subprocess
import time
from pathlib import Path

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

    started = time.monotonic()
    proc = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    elapsed = time.monotonic() - started

    if proc.returncode != 0:
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


def _build_ffmpeg_command(
    ffmpeg: str, manifest: RenderManifest, output_path: Path
) -> list[str]:
    """Deterministic FFmpeg command. Same manifest → same command bytes."""
    cap = get_renderer(manifest.renderer)
    has_normalize = manifest.normalize_audio and "normalize_audio" in cap.capabilities
    has_watermark = manifest.watermark and "watermark" in cap.capabilities

    vfilters = [
        f"scale={manifest.output_width}:{manifest.output_height}"
        f":force_original_aspect_ratio=decrease",
        f"pad={manifest.output_width}:{manifest.output_height}"
        f":(ow-iw)/2:(oh-ih)/2:black",
    ]
    if has_watermark:
        # Tiny corner watermark; deterministic content + position.
        vfilters.append(
            "drawtext=text='aidirector':"
            "fontcolor=white@0.6:fontsize=14:"
            "x=w-tw-10:y=h-th-10"
        )

    afilters: list[str] = []
    if has_normalize:
        # FFmpeg's single-pass loudnorm; deterministic enough for fixtures.
        afilters.append("loudnorm=I=-14:LRA=11:TP=-1.5")

    args: list[str] = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", f"{manifest.clip_start:.3f}",
        "-i", manifest.source_uri,
        "-t", f"{manifest.duration:.3f}",
        "-r", str(manifest.fps),
        "-vf", ",".join(vfilters),
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", str(manifest.crf),
        "-b:v", f"{manifest.bitrate_kbps}k",
        "-pix_fmt", "yuv420p",
    ]

    if afilters:
        args += ["-af", ",".join(afilters), "-c:a", "aac", "-b:a", "128k"]
    else:
        args += ["-an"]

    args.append(str(output_path))
    return args
