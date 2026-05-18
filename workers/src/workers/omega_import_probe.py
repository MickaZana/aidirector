"""Phase 0 ship-gate probe — prove OmegaClips imports inside Modal.

Returns the richer contract from the runbook (docs/runbooks/modal_hello_import.md).
This file is the canonical hello-import; the older `ping_intel` in
`modal_app.py` is kept for backward compat and points here.
"""
from __future__ import annotations

import os
import sys

import modal

from workers.modal_app import app, intel_image


@app.function(image=intel_image, timeout=60)
def omega_import_probe() -> dict[str, object]:
    """Phase 0 gate #2: confirm OmegaClips imports inside Modal."""
    sys.path.insert(0, "/intel")
    from football_pipeline.config import PipelineConfig

    cfg = PipelineConfig()
    return {
        "ok": True,
        "engine": "OmegaClips",
        "import": "football_pipeline.config.PipelineConfig",
        "submodule_commit": os.environ.get("INTEL_SUBMODULE_SHA", "unknown"),
        "python_version": sys.version.split()[0],
        "cwd": os.getcwd(),
        "mounted_path_exists": os.path.isdir("/intel/football_pipeline"),
        "config_class": type(cfg).__name__,
    }
