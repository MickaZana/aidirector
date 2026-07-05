"""Drive 4 9:16 renders against a real source video using the production adapters.

Audit-driven path: the HTTP API -> worker queue path isn't wired end-to-end yet
(see [routers/jobs.py:77-78](apps/api/src/api/routers/jobs.py#L77-L78)). The
render boundary itself is real — `services/intel/render_plan_adapter.render_clip`
shells out to ffmpeg via a validated `RenderManifest`. This script feeds that
boundary four manifests sliced across the source video.

Each manifest:
  - source_uri = the input video (anything ffmpeg can read; here `~/Downloads/movie.mp4`)
  - 1080×1920 (9:16), 30fps, ffmpeg_basic renderer, no captions, no watermark
  - clip windows = four evenly-spaced 8s slices across the source

Outputs land under `apps/api/_local_storage/four_vertical_clips/` (gitignored).
Exits 0 only if all four .mp4s are present and non-empty.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Make `api.*` importable when run from the repo with `uv run`.
SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from api.schemas.render_manifest import RenderManifest  # noqa: E402
from api.services.clip_format import (  # noqa: E402
    SHORT_FORM_DURATION_RANGE_S,
    pick_short_form_duration,
)
from api.services.intel.render_plan_adapter import render_clip  # noqa: E402
from api.services.transcribe import transcribe_to_srt  # noqa: E402
from api.services.viral_title import TitleHints, build_title, read_srt_text  # noqa: E402


def discover_source() -> Path:
    """Pick the source video. Honor SOURCE_VIDEO override, else default to
    the user's Downloads/movie.mp4 (Windows path)."""
    override = os.environ.get("SOURCE_VIDEO")
    if override:
        p = Path(override)
        if not p.exists():
            raise FileNotFoundError(f"SOURCE_VIDEO override missing: {p}")
        return p

    home = Path(os.environ.get("USERPROFILE") or Path.home())
    p = home / "Downloads" / "movie.mp4"
    if not p.exists():
        raise FileNotFoundError(
            f"No source video at {p}. Set SOURCE_VIDEO=<absolute path> to override."
        )
    return p


def probe_duration(path: Path) -> float:
    """Use ffprobe to read the source duration (seconds)."""
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not on PATH")
    out = subprocess.check_output(
        [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )
    return float(out.strip())


def _format_timecode(seconds: float) -> str:
    """MM:SS rendering for the title banner."""
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def build_manifests(
    *,
    source: Path,
    duration_s: float,
    srt_dir: Path,
    n: int = 4,
) -> list[RenderManifest]:
    """Slice the source into N short-form windows and build a manifest each.

    Per-clip duration comes from `services.clip_format.pick_short_form_duration`
    so the pack varies across the canonical 13–29 s short-form band instead
    of all being the same length.

    Window centers land at 1/(n+1), 2/(n+1), … of the runtime. That way the
    slices avoid the very start (titles) and very end (credits) of the source.

    Per-clip, we also call the ASR helper to produce an .srt under
    `srt_dir/clip_NN.srt` and burn both the title + subtitle into the
    manifest. ASR failures fall back to a single-cue placeholder SRT so
    the render still happens.
    """
    upload_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    srt_dir.mkdir(parents=True, exist_ok=True)

    lo_band, hi_band = SHORT_FORM_DURATION_RANGE_S
    print(f"short-form duration band: {lo_band:.0f}-{hi_band:.0f}s")

    manifests: list[RenderManifest] = []
    for i in range(n):
        idx = i + 1
        slice_len_s = pick_short_form_duration(idx, n)
        center = duration_s * idx / (n + 1)
        start = max(0.0, center - slice_len_s / 2)
        end = min(duration_s, start + slice_len_s)
        actual = end - start
        candidate_id = str(uuid.uuid4())
        render_job_id = str(uuid.uuid4())

        srt_path = srt_dir / f"clip_{idx:02d}.srt"
        print(f"  [{idx}/{n}] transcribing {start:.1f}s..{end:.1f}s -> {srt_path.name}")
        tr = transcribe_to_srt(source, start, end, srt_path)
        print(f"      engine={tr.engine} segments={tr.segments}")

        # Viral title pulled from ASR keywords + position. Falls back to
        # position-based templates when the slice has no keyword hits.
        transcript_text = read_srt_text(srt_path)
        title = build_title(
            TitleHints(
                transcript=transcript_text,
                index=idx,
                total=n,
                clip_start_s=start,
                source_duration_s=duration_s,
            )
        )
        print(f"      title={title!r}")

        manifests.append(
            RenderManifest(
                render_job_id=render_job_id,
                candidate_id=candidate_id,
                upload_id=upload_id,
                job_id=job_id,
                tenant_id=tenant_id,
                source_uri=str(source),
                clip_start=start,
                clip_end=end,
                duration=actual,
                platform="youtube_shorts",
                aspect_ratio="9:16",
                output_width=1080,
                output_height=1920,
                fps=30,
                bitrate_preset="high",
                bitrate_kbps=8000,
                crf=20,
                renderer="ffmpeg_basic",
                render_style="ffmpeg_basic",
                caption_mode="basic",
                crop_mode="center",
                watermark=False,
                normalize_audio=True,
                title=title,
                subtitle_uri=str(srt_path.resolve()),
                filename_template="clip_{idx}.mp4",
                output_filename=f"clip_{idx:02d}_9x16.mp4",
                execution_metadata={
                    "slice_index": idx,
                    "slice_center_s": center,
                    "asr_engine": tr.engine,
                    "asr_segments": tr.segments,
                },
            )
        )
    return manifests


def main() -> int:
    source = discover_source()
    print(f"source={source}")
    dur = probe_duration(source)
    print(f"duration_s={dur:.3f}")

    out_dir = (
        Path(__file__).resolve().parent / "_local_storage" / "four_vertical_clips"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"output_dir={out_dir}")
    srt_dir = out_dir / "srt"

    manifests = build_manifests(source=source, duration_s=dur, srt_dir=srt_dir)
    failures: list[str] = []
    results = []
    for i, m in enumerate(manifests, start=1):
        print(
            f"\n[{i}/{len(manifests)}] window=({m.clip_start:.2f}s..{m.clip_end:.2f}s)"
            f" -> {m.output_filename}"
        )
        res = render_clip(m, output_dir=out_dir, timeout_s=180.0)
        results.append(res)
        if res.status != "succeeded" or not res.output_path:
            failures.append(f"#{i} status={res.status} error={res.error!r}")
            continue
        out = Path(res.output_path)
        size = out.stat().st_size if out.exists() else 0
        print(
            f"  ok status={res.status} elapsed={res.elapsed_seconds:.2f}s"
            f" bytes={size:,}"
        )
        if size <= 0:
            failures.append(f"#{i} output empty: {out}")

    print("\n--- summary ---")
    for i, r in enumerate(results, start=1):
        print(
            f"#{i} {r.output_filename if False else Path(r.output_path or '').name}"
            f" status={r.status} bytes={r.bytes} elapsed={r.elapsed_seconds:.2f}s"
        )

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nALL 4 CLIPS RENDERED.")
    print(f"Open: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
