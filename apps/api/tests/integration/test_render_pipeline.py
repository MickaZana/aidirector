"""Integration test — full four-clip vertical render pipeline.

Skipped unless SOURCE_VIDEO env var points to a real video file.
Run manually or in a dedicated CI job that provides a test video:

    SOURCE_VIDEO=/path/to/match.mp4 uv run pytest tests/integration/ -v -m integration

What this validates end-to-end:
  - ffprobe reads the source duration
  - transcribe_to_srt produces a .srt per clip (real or fallback)
  - viral_title.build_title returns a non-empty string
  - RenderManifest construction succeeds with title + subtitle_uri populated
  - render_clip shells out to ffmpeg and produces a non-empty .mp4
  - All four clip files are present and > 0 bytes
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def source_video() -> Path:
    env = os.environ.get("SOURCE_VIDEO", "")
    if not env:
        pytest.skip("SOURCE_VIDEO not set — skipping integration render test")
    p = Path(env)
    if not p.exists():
        pytest.skip(f"SOURCE_VIDEO={env} does not exist")
    return p


@pytest.fixture(scope="module")
def source_duration(source_video: Path) -> float:
    import shutil
    import subprocess

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        pytest.skip("ffprobe not on PATH")
    out = subprocess.check_output(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(source_video)],
        text=True,
    )
    return float(out.strip())


def test_four_clips_render(source_video: Path, source_duration: float, tmp_path: Path):
    """Build 4 manifests and render each. All must succeed and be non-empty."""
    import shutil
    from api.schemas.render_manifest import RenderManifest
    from api.services.clip_format import pick_short_form_duration
    from api.services.intel.render_plan_adapter import render_clip
    from api.services.transcribe import transcribe_to_srt
    from api.services.viral_title import TitleHints, build_title, read_srt_text

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not on PATH")

    n = 4
    srt_dir = tmp_path / "srt"
    srt_dir.mkdir()
    out_dir = tmp_path / "clips"
    out_dir.mkdir()

    upload_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    failures: list[str] = []

    for i in range(n):
        idx = i + 1
        slice_len = pick_short_form_duration(idx, n)
        center = source_duration * idx / (n + 1)
        start = max(0.0, center - slice_len / 2)
        end = min(source_duration, start + slice_len)
        actual = end - start

        srt_path = srt_dir / f"clip_{idx:02d}.srt"
        tr = transcribe_to_srt(source_video, start, end, srt_path)
        transcript = read_srt_text(srt_path)
        title = build_title(TitleHints(
            transcript=transcript, index=idx, total=n,
            clip_start_s=start, source_duration_s=source_duration,
        ))

        assert isinstance(title, str) and title.strip(), f"clip {idx}: empty title"
        assert srt_path.exists(), f"clip {idx}: srt missing"

        manifest = RenderManifest(
            render_job_id=str(uuid.uuid4()),
            candidate_id=str(uuid.uuid4()),
            upload_id=upload_id,
            job_id=job_id,
            tenant_id=tenant_id,
            source_uri=str(source_video),
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
        )

        result = render_clip(manifest, output_dir=out_dir, timeout_s=180.0)

        if result.status != "succeeded":
            failures.append(f"clip {idx}: status={result.status} error={result.error}")
            continue

        out_file = Path(result.output_path)
        if not out_file.exists() or out_file.stat().st_size == 0:
            failures.append(f"clip {idx}: output empty or missing at {out_file}")

    assert not failures, "Render failures:\n" + "\n".join(failures)
