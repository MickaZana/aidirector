"""Modal application — defines images, mounts, secrets, and the function registry.

`packages/intel` (OmegaClips) is mounted into the image at /intel and added to
sys.path so workers can `from football_pipeline import ...` without a pyproject
in the submodule.

Phase 0 ship gate (#2): the `ping_intel` function below should succeed when
invoked remotely. That proves `football_pipeline` is importable from a Modal
worker — the foundational integration test.
"""
from __future__ import annotations

from pathlib import Path

import modal

# Resolve packages/intel from this file's location, not CWD, so `modal run`
# works no matter where it's invoked from.
# workers/src/workers/modal_app.py → parents[3] is the repo root.
_INTEL_DIR = Path(__file__).resolve().parents[3] / "packages" / "intel"

# OmegaClips heavy deps. Trim/extend based on what football_pipeline actually
# needs at runtime; this is a starting set derived from imports observed in
# packages/intel/football_pipeline/__init__.py and ocr_backends.py.
intel_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "tesseract-ocr", "libgl1", "libglib2.0-0")
    .pip_install(
        "opencv-python-headless>=4.10",
        "numpy>=2.0",
        "pytesseract>=0.3",
        "pillow>=11.0",
        "anthropic>=0.42",
        "boto3>=1.35",
        "pydantic>=2.9",
    )
    .add_local_dir(_INTEL_DIR, remote_path="/intel")
    .add_local_python_source("workers")
    .env({"PYTHONPATH": "/intel"})
)

app = modal.App("aidirector")

# Secret bundles — populate in Modal dashboard: `modal secret create aidirector ...`
secrets = [modal.Secret.from_name("aidirector")]


@app.function(image=intel_image, timeout=60)
def ping_intel() -> dict[str, str]:
    """Phase 0 ship gate (#2): confirm OmegaClips imports inside Modal."""
    import sys
    sys.path.insert(0, "/intel")

    from football_pipeline.config import PipelineConfig

    cfg = PipelineConfig()
    return {
        "ok": "true",
        "python": sys.version.split()[0],
        "intel_config_class": type(cfg).__name__,
    }


# Function registrations — actual implementations live in their own modules and
# are wired up here so Modal sees a single app graph.
from workers.analyzer import analyze_scene  # noqa: E402, F401
from workers.director import direct_render_plan  # noqa: E402, F401
from workers.renderers.ffmpeg_finisher import finish_with_ffmpeg  # noqa: E402, F401
from workers.renderers.caption_engine import render_captions  # noqa: E402, F401
from workers.renderers.auto_crop import auto_crop  # noqa: E402, F401
from workers.renderers.static_generator import render_static  # noqa: E402, F401
from workers.renderers.hyperframes import render_hyperframes  # noqa: E402, F401
from workers.renderers.remotion import render_remotion  # noqa: E402, F401
