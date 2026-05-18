"""Caption Engine — wraps OmegaClips RG-2 caption_generation + caption_render."""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def render_captions(job_id: str, scene_id: str, params: dict) -> dict:
    """Stub — wraps football_pipeline.caption_*. Phase 1."""
    raise NotImplementedError("Phase 1")
