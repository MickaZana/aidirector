"""Viral-style title generator for short-form clips.

We don't have a real LLM key wired locally and Anthropic is gated by env.
So this is a deterministic, template-driven generator that picks a title
template based on signals available without an LLM call:

  1. Keyword hits in the slice's ASR transcript (goal calls,
     setup language, save calls, etc.)
  2. The clip's position in the source (intro / mid / climax / outro)
  3. Index in a series (so a 4-clip pack feels like a pack, not 4 strays)

Output stays inside ~28 chars when possible so the drawtext width-fit
clamp doesn't shrink it below readable size. Uses ALL CAPS for the
pattern-interrupt word and a curiosity-gap construction.

Designed to be the single seam an LLM-backed generator can slot into
later (same input shape, same return type).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


# --- keyword buckets -------------------------------------------------------
# Order matters: first hit wins. Patterns are matched against lowercased
# transcript text, word-bounded to avoid false hits ("goal" vs "goalkeeper").

_GOAL_PATTERNS = (
    re.compile(r"\bgoal!?\b"),
    re.compile(r"\bit['’]?s in\b"),
    re.compile(r"\bput away\b"),
    re.compile(r"\bin the net\b"),
    re.compile(r"\bthe back of the net\b"),
    re.compile(r"\bhe scores\b"),
    re.compile(r"\bback of the net\b"),
    re.compile(r"\bfinish(?:es|ed)?\b.*\b(top|corner|net)\b"),
)

_SETUP_PATTERNS = (
    re.compile(r"\bset(?:s|ting)? up\b"),
    re.compile(r"\bplay(?:s|ed|ing)? in\b"),
    re.compile(r"\bthrough ball\b"),
    re.compile(r"\bbuild(?:s|ing|-)up\b"),
    re.compile(r"\bthread(?:s|ed)?\b"),
)

_SAVE_PATTERNS = (
    re.compile(r"\bsav(?:e|ed|es|ing)\b"),
    re.compile(r"\bdenied\b"),
    re.compile(r"\bkeep(?:s|er)?\b.*\b(stop|out|away)\b"),
    re.compile(r"\bclear(?:s|ed)?\b.*\bline\b"),
)

_SKILL_PATTERNS = (
    re.compile(r"\b(brilliant|stunning|outrageous|insane|class)\b"),
    re.compile(r"\bdribble\b"),
    re.compile(r"\bnutmeg\b"),
    re.compile(r"\bturn(?:s|ed)?\b.*\b(defender|man|him)\b"),
    re.compile(r"\bsilk(?:y|en)?\b"),
)

_FAIL_PATTERNS = (
    re.compile(r"\bmiss(?:ed|es)?\b"),
    re.compile(r"\bover the bar\b"),
    re.compile(r"\bwide of\b"),
    re.compile(r"\boff target\b"),
)


@dataclass(frozen=True)
class TitleHints:
    """Inputs to title selection."""

    transcript: str           # ASR text for the slice
    index: int                # 1-based position in the series
    total: int                # series size
    clip_start_s: float       # slice start in the source
    source_duration_s: float  # full source length


# --- template pools --------------------------------------------------------
# Each line is one template. {time} is replaced with MM:SS, {idx} with the
# 1-based clip number. Keep templates <= 30 chars where possible.

_GOAL_TITLES = (
    "GOAL! Watch this finish",
    "THIS is how you score",
    "Top corner, no chance",
    "He buried it. Wait for it.",
    "GOAL and the crowd LOSES it",
)

_SETUP_TITLES = (
    "Watch how this UNFOLDS",
    "Wait — THIS is the buildup",
    "How is this even open?",
    "The pass nobody saw",
    "From nothing to EVERYTHING",
)

_SAVE_TITLES = (
    "DENIED. Best save today",
    "Save of the season?",
    "He had NO right to save that",
    "How did he reach this?",
)

_SKILL_TITLES = (
    "Outrageous skill on the ball",
    "He made him LOOK silly",
    "Footwork you've never seen",
    "Did he really just do that?",
)

_FAIL_TITLES = (
    "HOW did he miss this?",
    "Open net — wait for the ending",
    "You had to score that",
)

# Position-based fallbacks (when no keywords hit) — bracket by where in
# the source the slice falls. Lean on curiosity-gap framing.
_OPENER_TITLES = (
    "It all started HERE",
    "The first sign of trouble",
    "Before the chaos",
)

_BUILDUP_TITLES = (
    "Watch the pattern build",
    "The tide turns",
    "Wait — momentum SHIFTS",
)

_CLIMAX_TITLES = (
    "THIS is the moment",
    "Peak chaos — clip {idx}",
    "Don't blink for this one",
)

_OUTRO_TITLES = (
    "The aftermath",
    "How it ended",
    "One more chance",
)


def _format_timecode(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def _pick_deterministic(pool: tuple[str, ...], seed_text: str) -> str:
    """Pick one template from the pool, seeded by transcript text so the
    same input always produces the same output (good for re-runs)."""
    h = hashlib.sha1(seed_text.encode("utf-8")).digest()
    return pool[h[0] % len(pool)]


def _category(transcript: str) -> str | None:
    """Return the keyword category for a transcript, or None."""
    text = (transcript or "").lower()
    if not text.strip():
        return None
    for pat in _GOAL_PATTERNS:
        if pat.search(text):
            return "goal"
    for pat in _SETUP_PATTERNS:
        if pat.search(text):
            return "setup"
    for pat in _SAVE_PATTERNS:
        if pat.search(text):
            return "save"
    for pat in _SKILL_PATTERNS:
        if pat.search(text):
            return "skill"
    for pat in _FAIL_PATTERNS:
        if pat.search(text):
            return "fail"
    return None


def _position_bucket(start_s: float, duration_s: float) -> str:
    """Bucket the clip's position in the source into a viral-template family."""
    if duration_s <= 0:
        return "climax"
    ratio = max(0.0, min(1.0, start_s / duration_s))
    if ratio < 0.20:
        return "opener"
    if ratio < 0.50:
        return "buildup"
    if ratio < 0.80:
        return "climax"
    return "outro"


def build_title(hints: TitleHints) -> str:
    """Pick a viral title for one clip.

    Stable for a given (transcript, index, position) — re-running the
    pipeline won't churn titles.
    """
    seed = f"{hints.index}|{hints.clip_start_s:.0f}|{hints.transcript}"

    cat = _category(hints.transcript)
    if cat == "goal":
        pool = _GOAL_TITLES
    elif cat == "setup":
        pool = _SETUP_TITLES
    elif cat == "save":
        pool = _SAVE_TITLES
    elif cat == "skill":
        pool = _SKILL_TITLES
    elif cat == "fail":
        pool = _FAIL_TITLES
    else:
        bucket = _position_bucket(hints.clip_start_s, hints.source_duration_s)
        pool = {
            "opener": _OPENER_TITLES,
            "buildup": _BUILDUP_TITLES,
            "climax": _CLIMAX_TITLES,
            "outro": _OUTRO_TITLES,
        }[bucket]

    chosen = _pick_deterministic(pool, seed)
    return chosen.format(idx=hints.index, time=_format_timecode(hints.clip_start_s))


def read_srt_text(srt_path: str | Path) -> str:
    """Helper: concatenate cue lines from an SRT into a single string for
    keyword matching. Skips index lines and timecode lines.
    """
    p = Path(srt_path)
    if not p.exists():
        return ""
    parts: list[str] = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.isdigit():
            continue
        if "-->" in line:
            continue
        parts.append(line)
    return " ".join(parts)
