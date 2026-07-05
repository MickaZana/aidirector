"""Feature flags — toggle risky features without a deploy.

Every flag has a default value in Settings (config.py). At runtime, the
flag can be overridden by:
  1. Environment variable (highest priority)
  2. JSON config file at FEATURE_FLAGS_PATH
  3. Settings default (lowest priority)

Usage:
    from api.feature_flags import flag

    if flag("use_modal_workers"):
        # deploy to Modal
    else:
        # use local RQ workers

Sprint 2 flags:
    use_modal_workers    — toggle between local RQ + Modal workers
    enable_llm_enrichment — toggle Anthropic Director Agent enrichment
    enforce_quotas       — toggle billing quota enforcement
    show_fixture_data    — toggle mock data on frontend pages
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.config import get_settings

_FLAGS_PATH = Path(os.environ.get("FEATURE_FLAGS_PATH", "feature_flags.json"))


def _load_override_file() -> dict[str, Any]:
    """Load feature flag overrides from JSON file, if it exists."""
    if _FLAGS_PATH.exists():
        try:
            with open(_FLAGS_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


@lru_cache(maxsize=1)
def _cached_overrides() -> dict[str, Any]:
    return _load_override_file()


def flag(name: str) -> bool:
    """Resolve a feature flag by name.

    Priority: env var > JSON file > settings default.
    """
    # 1. Environment variable override
    env_val = os.environ.get(f"FF_{name}")
    if env_val is not None:
        return env_val.lower() in ("1", "true", "yes")

    # 2. JSON file override
    overrides = _cached_overrides()
    if name in overrides:
        val = overrides[name]
        if isinstance(val, bool):
            return val

    # 3. Settings default
    settings = get_settings()
    attr = f"ff_{name}"
    default = getattr(settings, attr, None)
    if default is not None:
        return bool(default)

    return False


def invalidate_cache() -> None:
    """Clear the cached overrides (call after writing to the JSON file)."""
    _cached_overrides.cache_clear()
