"""Unified render worker.

The Director Plan's `render_style` is resolved (in apps/api/services/intel/
render_plan_adapter.resolve_render_spec) to a pipeline name. This worker
dispatches to the matching OmegaClips renderer:

  ffmpeg_finisher  -> football_pipeline.render_execution
  static_generator -> AI Director's own static_generator renderer
  hyperframes      -> AI Director's HyperFrames pipeline (phase 3)
  remotion         -> AI Director's Remotion pipeline (phase 3)

Phase 0 status: stub. Phase 1 wires ffmpeg_finisher; phase 2 adds static_generator.
"""
from __future__ import annotations

import modal

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=1200, memory=4096)
def render_clip_variant(
    render_job_id: str, tenant_slug: str
) -> dict[str, object]:
    """Phase 0 stub. Phase 1 reads RenderJob.settings and invokes the resolved pipeline."""
    raise NotImplementedError(
        "Phase 1 — wraps football_pipeline.render_execution.execute_render_manifest"
    )
