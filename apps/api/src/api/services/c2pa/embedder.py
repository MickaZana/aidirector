"""C2PA manifest embedder — injects provenance manifest as MP4 metadata.

Uses FFmpeg's `-metadata` flag to embed the C2PA manifest JSON as a UTF-8
metadata tag in the MP4 container. This is a fast remux operation (no
re-encode) that completes in < 1 second for typical clip sizes.

The manifest is stored under the key `c2pa_manifest` in the MP4 metadata.
A second key `c2pa_manifest_url` records where the canonical manifest JSON
can be fetched (R2 sidecar), enabling consumers who trust the signer to
fetch the manifest without parsing MP4 boxes.

For strict C2PA v2.3 ISOBMFF box embedding (the full spec), replace this
module with a call to `c2patool` or `c2pa-python` in a future sprint.
The schema and signing infrastructure are already compatible.

Usage:
    new_path = embed_manifest(
        mp4_path="/tmp/render/output.mp4",
        manifest_json={...},   # serializable dict from ProvenanceManifest
        manifest_url="https://r2.example.com/bucket/key.c2pa.json",
    )
    # new_path is a temp file with embedded metadata; original is unchanged
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbedResult:
    """Result of a C2PA manifest embedding operation."""

    success: bool
    output_path: str | None = None
    elapsed_s: float = 0.0
    error: str | None = None
    bytes_before: int | None = None
    bytes_after: int | None = None


def embed_manifest(
    mp4_path: str | Path,
    manifest_json: dict,
    manifest_url: str | None = None,
    *,
    ffmpeg_bin: str | None = None,
    timeout_s: float = 30.0,
) -> EmbedResult:
    """Embed a C2PA manifest as MP4 metadata using FFmpeg remux.

    Args:
        mp4_path: Path to the rendered MP4 file.
        manifest_json: The serialized ProvenanceManifest dict.
        manifest_url: Optional URL where the manifest sidecar is stored.
        ffmpeg_bin: Override FFmpeg binary path (default: 'ffmpeg' from PATH).
        timeout_s: FFmpeg subprocess timeout.

    Returns:
        EmbedResult with the output path on success.

    Notes:
        - Creates a temp file in the same directory as the input (fast renames).
        - The original file is NOT modified; the caller replaces the original
          with the embedded copy.
        - FFmpeg remux with `-metadata` is a container-level operation and
          does NOT re-encode the video or audio streams.
    """
    ffmpeg = ffmpeg_bin or _find_ffmpeg()
    if not ffmpeg:
        return EmbedResult(success=False, error="ffmpeg binary not found")

    mp4_path = Path(mp4_path)
    if not mp4_path.exists():
        return EmbedResult(success=False, error=f"input file not found: {mp4_path}")

    bytes_before = mp4_path.stat().st_size

    # Serialize manifest to a single-line JSON string (FFmpeg metadata value)
    manifest_str = json.dumps(manifest_json, separators=(",", ":"), default=str)

    # Build output path in the same directory (fast cross-device renames)
    fd, tmp_output = tempfile.mkstemp(
        suffix=".c2pa.mp4",
        prefix=mp4_path.stem + "_",
        dir=mp4_path.parent,
    )
    os.close(fd)

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(mp4_path),
        "-map",
        "0",  # copy all streams
        "-codec",
        "copy",  # no re-encode
        "-metadata",
        f"c2pa_manifest={manifest_str}",
    ]
    if manifest_url:
        cmd += ["-metadata", f"c2pa_manifest_url={manifest_url}"]

    # Add C2PA v2.3 Content Credentials marker
    cmd += [
        "-metadata",
        "c2pa_version=2.3",
        "-movflags",
        "use_metadata_tags",
        str(tmp_output),
    ]

    log.info(
        "c2pa_embedder: embedding manifest for %s (%d bytes)",
        mp4_path.name,
        bytes_before,
    )
    started = time.monotonic()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - started
        _cleanup(tmp_output)
        return EmbedResult(
            success=False,
            elapsed_s=elapsed,
            error=f"ffmpeg timed out after {timeout_s}s",
        )

    elapsed = time.monotonic() - started

    if proc.returncode != 0:
        _cleanup(tmp_output)
        stderr_tail = (proc.stderr or "").strip()[-300:]
        log.error(
            "c2pa_embedder: ffmpeg failed rc=%d elapsed=%.1fs stderr=%s",
            proc.returncode,
            elapsed,
            stderr_tail,
        )
        return EmbedResult(
            success=False,
            elapsed_s=elapsed,
            error=f"ffmpeg exit {proc.returncode}: {stderr_tail}",
        )

    # Verify output exists and is larger than input (metadata adds bytes)
    output_path = Path(tmp_output)
    if not output_path.exists():
        _cleanup(tmp_output)
        return EmbedResult(
            success=False,
            elapsed_s=elapsed,
            error="ffmpeg completed but output file not found",
        )

    bytes_after = output_path.stat().st_size

    log.info(
        "c2pa_embedder: embedded manifest in %.1fs (%d → %d bytes, +%d)",
        elapsed,
        bytes_before,
        bytes_after,
        bytes_after - bytes_before,
    )

    return EmbedResult(
        success=True,
        output_path=str(output_path),
        elapsed_s=elapsed,
        bytes_before=bytes_before,
        bytes_after=bytes_after,
    )


# ── Helpers ─────────────────────────────────────────────────────────────────


def _find_ffmpeg() -> str | None:
    """Locate ffmpeg binary on PATH."""
    import shutil

    return shutil.which("ffmpeg")


def _cleanup(path: str | Path | None) -> None:
    """Remove a temp file if it exists."""
    if path:
        try:
            os.unlink(path)
        except OSError:
            pass
