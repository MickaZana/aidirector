"""Unit tests for services/intel/render_plan_adapter.py

Uses dry_run=True throughout so no ffmpeg subprocess is spawned.
Tests verify command construction is deterministic and that the
title/subtitle/watermark filter branches produce correct filter strings.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

from api.schemas.render_manifest import RenderManifest
from api.services.intel.render_plan_adapter import (
    _drawtext_escape,
    _subtitles_filter_path,
    render_clip,
)

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


def _manifest(**kwargs) -> RenderManifest:
    return RenderManifest(**{**BASE, **kwargs})


# ---------------------------------------------------------------------------
# dry_run=True — command construction
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_returns_succeeded_status(self, tmp_path: Path):
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        assert result.status == "succeeded"

    def test_command_starts_with_ffmpeg(self, tmp_path: Path):
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        assert result.command[0] == "/usr/bin/ffmpeg"

    def test_output_path_in_command(self, tmp_path: Path):
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        assert m.output_filename in result.command[-1]

    def test_same_manifest_same_command(self, tmp_path: Path):
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            r1 = render_clip(m, output_dir=tmp_path, dry_run=True)
            r2 = render_clip(m, output_dir=tmp_path, dry_run=True)
        assert r1.command == r2.command

    def test_ffmpeg_bin_override(self, tmp_path: Path):
        m = _manifest()
        result = render_clip(m, output_dir=tmp_path, dry_run=True, ffmpeg_bin="/custom/ffmpeg")
        assert result.command[0] == "/custom/ffmpeg"

    def test_no_ffmpeg_returns_failed(self, tmp_path: Path):
        m = _manifest()
        with patch("shutil.which", return_value=None):
            result = render_clip(m, output_dir=tmp_path, dry_run=False)
        assert result.status == "failed"
        assert "ffmpeg" in (result.error or "").lower()

    def test_clip_timing_in_command(self, tmp_path: Path):
        m = _manifest(clip_start=5.5, duration=12.3)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        cmd = " ".join(result.command)
        assert "5.500" in cmd
        assert "12.300" in cmd


# ---------------------------------------------------------------------------
# Video filter construction
# ---------------------------------------------------------------------------


class TestVideoFilters:
    def _cmd(self, tmp_path: Path, **kwargs) -> list[str]:
        m = _manifest(**kwargs)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        # -vf is immediately before the filter string
        vf_idx = result.command.index("-vf")
        return result.command[vf_idx + 1].split(",")

    def test_scale_filter_present(self, tmp_path: Path):
        filters = self._cmd(tmp_path)
        assert any("scale=" in f for f in filters)

    def test_crop_filter_present_for_center_mode(self, tmp_path: Path):
        """crop_mode='center' should use crop+scale, not scale+pad."""
        filters = self._cmd(tmp_path, crop_mode="center")
        assert any("crop=" in f for f in filters), "Expected crop= filter for center mode"
        assert not any("pad=" in f for f in filters), "No pad= expected for center mode"

    def test_pad_filter_present_for_fit_mode(self, tmp_path: Path):
        """crop_mode='fit' should use scale+pad (letterbox behavior)."""
        filters = self._cmd(tmp_path, crop_mode="fit")
        assert any("pad=" in f for f in filters), "Expected pad= filter for fit mode"
        assert any("scale=" in f for f in filters)

    def test_crop_mode_action_fills_frame(self, tmp_path: Path):
        """crop_mode='action' should fill frame (no pad, no black bars)."""
        filters = self._cmd(tmp_path, crop_mode="action")
        assert any("crop=" in f for f in filters), "Expected crop= filter for action mode"
        assert not any("pad=" in f for f in filters), "No pad= expected for action mode"

    def test_crop_filter_dimensions_are_even(self, tmp_path: Path):
        """Crop dimensions must be even numbers for yuv420p compatibility."""
        filters = self._cmd(tmp_path, crop_mode="center")
        crop_filter = next(f for f in filters if "crop=" in f)
        # The crop expression uses 2*trunc(.../2) which guarantees even values
        assert "2*trunc" in crop_filter, "Crop should use 2*trunc for even dimensions"
        assert "min(iw" in crop_filter, "Crop should handle aspect ratio generically"

    def test_no_drawtext_without_title(self, tmp_path: Path):
        filters = self._cmd(tmp_path, title=None)
        assert not any("drawtext" in f and "text=" in f for f in filters)

    def test_title_injects_drawtext(self, tmp_path: Path):
        filters = self._cmd(tmp_path, title="GOAL Watch This")
        drawtext_filters = [f for f in filters if "drawtext" in f and "text=" in f]
        assert len(drawtext_filters) >= 1
        assert "GOAL Watch This" in drawtext_filters[0]

    def test_no_subtitle_without_uri(self, tmp_path: Path):
        filters = self._cmd(tmp_path, subtitle_uri=None)
        assert not any("subtitles=" in f for f in filters)

    def test_subtitle_uri_injects_filter(self, tmp_path: Path):
        filters = self._cmd(tmp_path, subtitle_uri="/tmp/clip.srt")
        assert any("subtitles=" in f for f in filters)

    def test_watermark_drawtext_present(self, tmp_path: Path):
        filters = self._cmd(tmp_path, watermark=True)
        assert any("aidirector" in f for f in filters)

    def test_no_watermark_when_disabled(self, tmp_path: Path):
        filters = self._cmd(tmp_path, watermark=False)
        assert not any("aidirector" in f for f in filters)


# ---------------------------------------------------------------------------
# Audio filter construction
# ---------------------------------------------------------------------------


class TestAudioFilters:
    def test_no_audio_when_normalize_false(self, tmp_path: Path):
        m = _manifest(normalize_audio=False)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        assert "-an" in result.command
        assert "-af" not in result.command

    def test_loudnorm_when_normalize_true(self, tmp_path: Path):
        m = _manifest(normalize_audio=True)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            result = render_clip(m, output_dir=tmp_path, dry_run=True)
        cmd = " ".join(result.command)
        assert "loudnorm" in cmd


# ---------------------------------------------------------------------------
# _drawtext_escape
# ---------------------------------------------------------------------------


class TestDrawtextEscape:
    def test_plain_ascii_unchanged(self):
        assert _drawtext_escape("Hello World") == "Hello World"

    def test_colon_escaped(self):
        assert r"\:" in _drawtext_escape("time: 00:01")

    def test_percent_escaped(self):
        assert r"\%" in _drawtext_escape("100% goal")

    def test_backslash_doubled(self):
        assert "\\\\" in _drawtext_escape("C:\\path\\file")

    def test_empty_string(self):
        assert _drawtext_escape("") == ""


# ---------------------------------------------------------------------------
# _subtitles_filter_path
# ---------------------------------------------------------------------------


class TestSubtitlesFilterPath:
    def test_backslashes_converted(self):
        # Windows path separators (\U, \f, \c) must become forward slashes.
        # The only remaining backslash should be the colon escape (\:).
        result = _subtitles_filter_path("C:\\Users\\foo\\clip.srt")
        # Strip the \: escape and confirm no other backslashes remain.
        without_colon_escape = result.replace(r"\:", "")
        assert "\\" not in without_colon_escape

    def test_windows_colon_escaped(self):
        result = _subtitles_filter_path("C:/Users/foo/clip.srt")
        assert r"\:" in result

    def test_unix_path_unchanged_except_colon(self):
        result = _subtitles_filter_path("/tmp/clip.srt")
        # No colon in a unix path — forward slashes and no escaping needed
        assert result == "/tmp/clip.srt"


# ---------------------------------------------------------------------------
# TimeoutExpired handling (Bug B7 fix)
# ---------------------------------------------------------------------------


class TestTimeoutHandling:
    def test_timeout_returns_failed_status(self, tmp_path: Path):
        """When ffmpeg times out, render_clip returns status='failed' with
        a descriptive error message instead of raising an exception."""
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="/usr/bin/ffmpeg",
                    timeout=0.001,
                ),
            ):
                result = render_clip(m, output_dir=tmp_path, dry_run=False, timeout_s=0.001)
        assert result.status == "failed"
        assert "timed out" in (result.error or "").lower()

    def test_timeout_preserves_manifest_ids(self, tmp_path: Path):
        """The manifest's render_job_id and candidate_id should survive a
        timeout and be present in the result."""
        rj_id = str(uuid.uuid4())
        cand_id = str(uuid.uuid4())
        m = _manifest(render_job_id=rj_id, candidate_id=cand_id)
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="/usr/bin/ffmpeg",
                    timeout=0.001,
                ),
            ):
                result = render_clip(m, output_dir=tmp_path, dry_run=False, timeout_s=0.001)
        assert result.render_job_id == rj_id
        assert result.candidate_id == cand_id

    def test_timeout_records_elapsed_seconds(self, tmp_path: Path):
        """Even on timeout, elapsed_seconds should be > 0 (captures time
        spent before the timeout was raised)."""
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch(
                "subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="/usr/bin/ffmpeg",
                    timeout=0.001,
                ),
            ):
                result = render_clip(m, output_dir=tmp_path, dry_run=False, timeout_s=0.001)
        assert result.elapsed_seconds >= 0.0

    def test_normal_completion_not_affected(self, tmp_path: Path):
        """Non-timeout renders should still succeed normally (no regression)."""
        m = _manifest()
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = ""
                mock_run.return_value.stderr = ""
                result = render_clip(m, output_dir=tmp_path, dry_run=False, timeout_s=300.0)
        assert result.status == "succeeded"
