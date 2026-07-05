"""Unit tests for services/transcribe.py — no ffmpeg or faster-whisper required."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from api.services.transcribe import (
    TranscriptionResult,
    _format_srt_ts,
    _write_fallback_srt,
    transcribe_to_srt,
)


class TestFormatSrtTs:
    def test_zero(self):
        assert _format_srt_ts(0.0) == "00:00:00,000"

    def test_one_second(self):
        assert _format_srt_ts(1.0) == "00:00:01,000"

    def test_one_minute(self):
        assert _format_srt_ts(60.0) == "00:01:00,000"

    def test_one_hour(self):
        assert _format_srt_ts(3600.0) == "01:00:00,000"

    def test_fractional_seconds(self):
        assert _format_srt_ts(1.5) == "00:00:01,500"

    def test_negative_clamped_to_zero(self):
        assert _format_srt_ts(-1.0) == "00:00:00,000"

    def test_complex(self):
        # 1h 2m 3.456s
        assert _format_srt_ts(3600 + 120 + 3.456) == "01:02:03,456"


class TestWriteFallbackSrt:
    def test_creates_file(self, tmp_path: Path):
        srt = tmp_path / "fallback.srt"
        _write_fallback_srt(srt, 5.0, "test message")
        assert srt.exists()

    def test_contains_message(self, tmp_path: Path):
        srt = tmp_path / "fallback.srt"
        _write_fallback_srt(srt, 5.0, "hello world")
        assert "hello world" in srt.read_text(encoding="utf-8")

    def test_contains_timecode_arrow(self, tmp_path: Path):
        srt = tmp_path / "fallback.srt"
        _write_fallback_srt(srt, 3.0, "msg")
        assert "-->" in srt.read_text(encoding="utf-8")

    def test_zero_duration_clamps_end_to_half_second(self, tmp_path: Path):
        srt = tmp_path / "fallback.srt"
        _write_fallback_srt(srt, 0.0, "msg")
        content = srt.read_text(encoding="utf-8")
        # end timestamp should be 0.5s
        assert "00:00:00,500" in content

    def test_utf8_encoding(self, tmp_path: Path):
        srt = tmp_path / "fallback.srt"
        _write_fallback_srt(srt, 2.0, "café résumé")
        content = srt.read_text(encoding="utf-8")
        assert "café" in content


class TestTranscribeToSrt:
    def test_fallback_when_no_model(self, tmp_path: Path):
        """When faster-whisper is not installed, fallback SRT is written."""
        srt = tmp_path / "out.srt"
        with patch("api.services.transcribe._load_model", return_value=None):
            result = transcribe_to_srt(
                Path("/fake/source.mp4"), 0.0, 10.0, srt
            )
        assert result.engine == "fallback"
        assert result.segments == 1
        assert srt.exists()
        assert "transcription unavailable" in srt.read_text(encoding="utf-8").lower()

    def test_fallback_on_ffmpeg_failure(self, tmp_path: Path):
        """Audio extraction failure writes fallback SRT, does not raise."""
        srt = tmp_path / "out.srt"
        mock_model = MagicMock()
        with patch("api.services.transcribe._load_model", return_value=mock_model):
            with patch(
                "api.services.transcribe._extract_audio_slice",
                side_effect=RuntimeError("ffmpeg not on PATH"),
            ):
                result = transcribe_to_srt(Path("/fake/source.mp4"), 0.0, 5.0, srt)
        assert result.engine == "fallback"
        assert srt.exists()

    def test_fallback_on_model_crash(self, tmp_path: Path):
        """Model.transcribe raising an exception writes fallback, does not raise."""
        srt = tmp_path / "out.srt"
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("CUDA OOM")
        with patch("api.services.transcribe._load_model", return_value=mock_model):
            with patch("api.services.transcribe._extract_audio_slice"):
                result = transcribe_to_srt(Path("/fake/source.mp4"), 0.0, 5.0, srt)
        assert result.engine == "fallback"
        assert srt.exists()

    def test_fallback_on_no_speech(self, tmp_path: Path):
        """Empty segment list writes fallback SRT."""
        srt = tmp_path / "out.srt"
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([]), MagicMock())
        with patch("api.services.transcribe._load_model", return_value=mock_model):
            with patch("api.services.transcribe._extract_audio_slice"):
                result = transcribe_to_srt(Path("/fake/source.mp4"), 0.0, 5.0, srt)
        assert result.engine == "fallback"
        content = srt.read_text(encoding="utf-8")
        assert "no speech" in content.lower()

    def test_real_segments_written(self, tmp_path: Path):
        """Valid segments produce a proper SRT with per-cue timestamps."""
        srt = tmp_path / "out.srt"
        seg1 = MagicMock(start=0.5, end=2.0, text=" Hello world")
        seg2 = MagicMock(start=2.5, end=4.0, text=" Second cue")
        mock_model = MagicMock()
        mock_model.transcribe.return_value = (iter([seg1, seg2]), MagicMock())
        with patch("api.services.transcribe._load_model", return_value=mock_model):
            with patch("api.services.transcribe._extract_audio_slice"):
                result = transcribe_to_srt(Path("/fake/source.mp4"), 0.0, 5.0, srt)
        assert result.engine == "faster-whisper"
        assert result.segments == 2
        content = srt.read_text(encoding="utf-8")
        assert "Hello world" in content
        assert "Second cue" in content
        assert "-->" in content

    def test_custom_fallback_text(self, tmp_path: Path):
        srt = tmp_path / "out.srt"
        with patch("api.services.transcribe._load_model", return_value=None):
            result = transcribe_to_srt(
                Path("/fake/source.mp4"), 0.0, 3.0, srt,
                fallback_text="[CUSTOM FALLBACK]",
            )
        assert "[CUSTOM FALLBACK]" in srt.read_text(encoding="utf-8")

    def test_creates_parent_dirs(self, tmp_path: Path):
        srt = tmp_path / "deep" / "nested" / "out.srt"
        with patch("api.services.transcribe._load_model", return_value=None):
            transcribe_to_srt(Path("/fake/source.mp4"), 0.0, 3.0, srt)
        assert srt.exists()

    def test_result_duration_matches_slice(self, tmp_path: Path):
        srt = tmp_path / "out.srt"
        with patch("api.services.transcribe._load_model", return_value=None):
            result = transcribe_to_srt(Path("/fake/source.mp4"), 5.0, 17.0, srt)
        assert result.duration_s == pytest.approx(12.0)
