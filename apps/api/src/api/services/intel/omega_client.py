"""OmegaClips submodule client — read-only metadata helpers.

Used by routers/health checks. Does not import `football_pipeline.*`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _find_repo_root() -> Path:
    """Walk up from this file until we find a .git directory or pyproject.toml.

    Replaces the fragile ``parents[6]`` pattern that broke when the
    directory structure changed. This approach works regardless of how
    deeply the file is nested or whether the project is mounted at a
    non-standard path (e.g. inside a Modal or Docker container).
    """
    current = Path(__file__).resolve().parent
    for _ in range(20):  # safety cap: don't walk past filesystem root
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Last-resort fallback: the old known relative depth. This survives
    # in case the .git dir isn't available (e.g. git-worktree, shallow clone).
    return Path(__file__).resolve().parents[6]


_INTEL_DIR = _find_repo_root() / "packages" / "intel"


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
