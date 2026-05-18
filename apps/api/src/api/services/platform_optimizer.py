"""Basic platform optimizer.

Maps each platform target to its render constraints. The Director Agent uses
this to constrain the variants it emits; renderer workers use it to set FFmpeg
params. No ML here — explicit tables only.

This is the "build interfaces only" version: real platform scoring (per the
capability map line 49, status C) lives behind a future ML model. Today the
optimizer is a lookup.
"""
from __future__ import annotations

from typing import Literal, TypedDict

from api.schemas.director_plan import AspectRatio, PlatformTarget


class PlatformPreset(TypedDict):
    aspect_ratio: AspectRatio
    duration_cap_s: int
    bitrate_kbps: int
    resolution: tuple[int, int]
    safe_zone_top_pct: int
    safe_zone_bottom_pct: int
    filename_template: str
    crf: int


PLATFORM_PRESETS: dict[PlatformTarget, PlatformPreset] = {
    "youtube_shorts": {
        "aspect_ratio": "9:16",
        "duration_cap_s": 60,
        "bitrate_kbps": 8000,
        "resolution": (1080, 1920),
        "safe_zone_top_pct": 12,
        "safe_zone_bottom_pct": 18,
        "filename_template": "{tenant}_{candidate}_yt_shorts.mp4",
        "crf": 21,
    },
    "tiktok": {
        "aspect_ratio": "9:16",
        "duration_cap_s": 60,
        "bitrate_kbps": 6000,
        "resolution": (1080, 1920),
        "safe_zone_top_pct": 10,
        "safe_zone_bottom_pct": 22,
        "filename_template": "{tenant}_{candidate}_tiktok.mp4",
        "crf": 22,
    },
    "instagram_reels": {
        "aspect_ratio": "9:16",
        "duration_cap_s": 90,
        "bitrate_kbps": 5500,
        "resolution": (1080, 1920),
        "safe_zone_top_pct": 12,
        "safe_zone_bottom_pct": 20,
        "filename_template": "{tenant}_{candidate}_reels.mp4",
        "crf": 22,
    },
    "x": {
        "aspect_ratio": "16:9",
        "duration_cap_s": 140,
        "bitrate_kbps": 5000,
        "resolution": (1920, 1080),
        "safe_zone_top_pct": 8,
        "safe_zone_bottom_pct": 10,
        "filename_template": "{tenant}_{candidate}_x.mp4",
        "crf": 23,
    },
}


def get_preset(platform: PlatformTarget) -> PlatformPreset:
    return PLATFORM_PRESETS[platform]


def filename_for(platform: PlatformTarget, tenant_slug: str, candidate_id: str) -> str:
    return PLATFORM_PRESETS[platform]["filename_template"].format(
        tenant=tenant_slug, candidate=candidate_id
    )


def supported_platforms() -> list[PlatformTarget]:
    return list(PLATFORM_PRESETS.keys())
