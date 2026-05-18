"""OmegaClips submodule client — read-only metadata helpers.

Used by routers/health checks. Does not import `football_pipeline.*`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_INTEL_DIR = Path(__file__).resolve().parents[5] / "packages" / "intel"


def submodule_sha() -> str | None:
    """Return the current submodule HEAD SHA or None if not a git checkout."""
    if not _INTEL_DIR.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(_INTEL_DIR), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def submodule_path() -> Path:
    return _INTEL_DIR


def is_populated() -> bool:
    """Check the submodule directory actually has football_pipeline inside."""
    return (_INTEL_DIR / "football_pipeline" / "__init__.py").exists()
