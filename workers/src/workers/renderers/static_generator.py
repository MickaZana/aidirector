"""Static Generator — NEW pipeline, not in OmegaClips.

Renders quote cards, stat overlays, score graphics, and thumbnail-like slides
from typed StaticGeneratorParams. Pillow-based; targets ~4s video segments that
the Finisher will splice into the final timeline.
"""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=120, memory=1024)
def render_static(job_id: str, scene_id: str, params: dict) -> dict:
    """Stub — Phase 2. Templates: quote_card, stat_overlay, score_graphic, thumbnail."""
    raise NotImplementedError("Phase 2")
