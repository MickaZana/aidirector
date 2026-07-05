"""ASR helper — turns a slice of a video into a burn-ready .srt file.

Uses `faster-whisper` (CTranslate2 inference) when available because it's
the lightest CPU path that still produces usable per-segment timestamps.
Falls back to a one-line "transcription unavailable" SRT so the renderer
still has a file to burn — the burn pipeline never silently no-ops.

The slice (start..end) is extracted with ffmpeg into a temporary wav so the
model sees only the relevant audio, and so the returned SRT timestamps are
already relative to the clip (no post-shift needed at render time).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Cached module instance — loading the tiny.en model takes ~1.5s on a cold
# start. Most callers transcribe multiple clips in a row.
_MODEL = None
_MODEL_SIZE = "tiny.en"


@dataclass(frozen=True)
class TranscriptionResult:
    srt_path: Path
    engine: str  # "faster-whisper" | "fallback"
    segments: int
    duration_s: float


def _format_srt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"


def _write_fallback_srt(out_srt: Path, end_s: float, message: str) -> None:
    """One-cue placeholder so the renderer always has something to burn."""
    out_srt.write_text(
        "\n".join(
            [
                "1",
                f"{_format_srt_ts(0.0)} --> {_format_srt_ts(max(0.5, end_s))}",
                message,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _extract_audio_slice(
    source: Path,
    start_s: float,
    end_s: float,
    wav_path: Path,
    *,
    ffmpeg_bin: str | None = None,
) -> None:
    """Extract a mono 16kHz wav slice — Whisper's preferred input."""
    ffmpeg = ffmpeg_bin or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not on PATH")
    proc = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-ss", f"{start_s:.3f}",
            "-i", str(source),
            "-t", f"{end_s - start_s:.3f}",
            "-ac", "1",
            "-ar", "16000",
            "-vn",
            str(wav_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg audio extract failed (rc={proc.returncode}): "
            f"{proc.stderr.strip().splitlines()[-3:]}"
        )


def _load_model():
    """Lazy-load the faster-whisper model. Returns None if unavailable."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    # int8 quant on CPU — fastest path that still produces usable output for
    # English speech. Model is auto-downloaded to the HF cache on first use
    # (~75MB for tiny.en).
    _MODEL = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    return _MODEL


def transcribe_to_srt(
    source: Path,
    start_s: float,
    end_s: float,
    out_srt: Path,
    *,
    language: str = "en",
    fallback_text: str | None = None,
    ffmpeg_bin: str | None = None,
) -> TranscriptionResult:
    """Transcribe a slice of `source` between [start_s, end_s] to an SRT.

    On success: `out_srt` contains real per-segment captions with
    clip-relative timestamps starting at 00:00:00,000.

    On failure (no faster-whisper, no audio, model crash): writes a single-
    cue fallback SRT so the renderer's `subtitles=` filter still finds a
    file. `fallback_text` controls what that cue says; default is a clear
    "Transcription unavailable" notice.
    """
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, end_s - start_s)

    model = _load_model()
    if model is None:
        msg = fallback_text or "[transcription unavailable — install faster-whisper]"
        log.warning("transcribe: faster-whisper unavailable; writing fallback SRT for %s", source)
        _write_fallback_srt(out_srt, duration, msg)
        return TranscriptionResult(out_srt, "fallback", 1, duration)

    with tempfile.TemporaryDirectory(prefix="aidirector_asr_") as td:
        wav = Path(td) / "slice.wav"
        try:
            _extract_audio_slice(source, start_s, end_s, wav, ffmpeg_bin=ffmpeg_bin)
        except Exception as exc:
            msg = fallback_text or f"[audio extraction failed: {exc.__class__.__name__}]"
            log.warning("transcribe: audio extraction failed for %s: %s", source, exc)
            _write_fallback_srt(out_srt, duration, msg)
            return TranscriptionResult(out_srt, "fallback", 1, duration)

        try:
            segments, _info = model.transcribe(
                str(wav),
                language=language,
                vad_filter=True,
                beam_size=1,
                condition_on_previous_text=False,
            )
            cues: list[tuple[float, float, str]] = []
            for seg in segments:
                txt = (seg.text or "").strip()
                if not txt:
                    continue
                # Clamp to clip bounds so a model overshoot doesn't push the
                # last cue past clip end.
                start = max(0.0, min(seg.start, duration))
                end = max(start + 0.1, min(seg.end, duration))
                cues.append((start, end, txt))
        except Exception as exc:
            msg = fallback_text or f"[ASR failed: {exc.__class__.__name__}]"
            log.warning("transcribe: model.transcribe raised %s for %s", type(exc).__name__, source)
            _write_fallback_srt(out_srt, duration, msg)
            return TranscriptionResult(out_srt, "fallback", 1, duration)

    if not cues:
        msg = fallback_text or "[no speech detected]"
        log.info("transcribe: no speech detected in %s [%.1f–%.1f s]", source, start_s, end_s)
        _write_fallback_srt(out_srt, duration, msg)
        return TranscriptionResult(out_srt, "fallback", 1, duration)

    lines: list[str] = []
    for i, (s, e, txt) in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_format_srt_ts(s)} --> {_format_srt_ts(e)}")
        lines.append(txt)
        lines.append("")
    out_srt.write_text("\n".join(lines), encoding="utf-8")
    return TranscriptionResult(out_srt, "faster-whisper", len(cues), duration)
