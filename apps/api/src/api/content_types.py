"""Shared content type contract independent of intelligence adapters."""
from __future__ import annotations

from typing import Literal

ContentType = Literal["football", "basketball", "podcast"]


def normalize_content_type(value: str | None) -> ContentType:
    value = (value or "football").strip().lower()
    if value == "podcast":
        return "podcast"
    if value == "basketball":
        return "basketball"
    return "football"
