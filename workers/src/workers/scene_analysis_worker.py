"""Scene analysis worker.

Wraps OmegaClips orchestrator. This is the only place outside
apps/api/services/intel/ that imports `football_pipeline.*`.

Phase 0 status: stub. Phase 1: download from R2, run
`FootballPipelineOrchestrator.run_full_pipeline`, parse artifacts, return
SceneAnalysisResult.
"""
from __future__ import annotations

import modal

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=1800, memory=8192)
def analyze_video(upload_id: str, source_r2_key: str, tenant_slug: str) -> dict[str, object]:
    """Phase 0 stub. Phase 1 will:
    1. download source_r2_key to /tmp/{upload_id}.mp4
    2. build PipelineConfig with tenant overrides
    3. orchestrator.run_full_pipeline()
    4. read scenes from workspace artifacts
    5. return shape matching api.services.intel.SceneAnalysisResult
    """
    raise NotImplementedError("Phase 1 — see plan §9 and docs/omega_capability_map.md")
