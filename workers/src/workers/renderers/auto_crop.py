"""Auto-Crop — wraps OmegaClips RG-5 dynamic_crop_engine."""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def auto_crop(job_id: str, scene_id: str, params: dict) -> dict:
    """Stub — wraps football_pipeline.dynamic_crop_engine. Phase 1."""
    raise NotImplementedError("Phase 1")
