"""Remotion Renderer — NEW pipeline, not in OmegaClips.

Cinematic/branded templates rendered via Remotion (Node + headless Chromium).
Modal CPU first; GPU only when motion-heavy templates need it.
"""
from __future__ import annotations

import modal

from workers.modal_app import app, secrets

remotion_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "chromium")
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_22.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g @remotion/cli@4",
    )
)


@app.function(image=remotion_image, secrets=secrets, timeout=1200, memory=8192)
def render_remotion(job_id: str, scene_id: str, params: dict) -> dict:
    """Stub — Phase 3."""
    raise NotImplementedError("Phase 3")
