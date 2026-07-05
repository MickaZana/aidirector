"""Canonical duration defaults for the two clip families.

The pipeline produces two flavours of output:
  - SHORT-FORM (vertical, e.g. 9:16 for Reels/Shorts/TikTok)
  - LONG-FORM (horizontal, e.g. 16:9 for YouTube long-form / podcasts)

Each family has a sensible duration band. Picking exactly one number per
band would make a 4-clip pack feel uniform; instead, callers ask for the
i-th of N clips and we interpolate across the band so the pack varies.

These constants are the single source of truth — when the orchestrator
gets wired (HTTP -> queue -> worker), it should import from here rather
than hard-coding magic numbers in the manifest builder.
"""
from __future__ import annotations

from typing import Final

# (min_s, max_s). Inclusive on both ends.
SHORT_FORM_DURATION_RANGE_S: Final[tuple[float, float]] = (13.0, 29.0)
LONG_FORM_DURATION_RANGE_S: Final[tuple[float, float]] = (240.0, 480.0)  # 4–8 min

# Defaults for "give me one clip" callers that don't have a pack context.
SHORT_FORM_DEFAULT_DURATION_S: Final[float] = 21.0  # mid-band
LONG_FORM_DEFAULT_DURATION_S: Final[float] = 360.0  # 6 min, mid-band


def _interpolate(index: int, total: int, lo: float, hi: float) -> float:
    """Pick the i-th value of N across [lo, hi].

    index is 1-based to match how clips are numbered in the rest of the
    pipeline ("clip 1 of 4"). For total==1, returns the midpoint.
    """
    if total < 1:
        raise ValueError(f"total must be >= 1, got {total}")
    if not (1 <= index <= total):
        raise ValueError(f"index {index} out of range for total={total}")
    if total == 1:
        return (lo + hi) / 2.0
    span = hi - lo
    return lo + (index - 1) * span / (total - 1)


def pick_short_form_duration(index: int, total: int) -> float:
    """Pick the i-th of N short-form durations across the canonical band."""
    lo, hi = SHORT_FORM_DURATION_RANGE_S
    return _interpolate(index, total, lo, hi)


def pick_long_form_duration(index: int, total: int) -> float:
    """Pick the i-th of N long-form durations across the canonical band."""
    lo, hi = LONG_FORM_DURATION_RANGE_S
    return _interpolate(index, total, lo, hi)
