"""Adapter: AI Director scene analysis contract.

The real work runs in `workers.scene_analysis_worker`. This module defines
the contract `analyze_video(upload_id, source_uri) -> SceneAnalysisResult`
and exposes a stub for tests/dev.

Production wiring: control plane enqueues a Modal job; worker calls
`football_pipeline.orchestrator.FootballPipelineOrchestrator.run_full_pipeline`,
reads the resulting JSON artifacts, builds a SceneAnalysisResult, and writes
scene rows. The worker is what imports `football_pipeline.*`.
"""
from __future__ import annotations

from api.services.intel.capability_registry import SceneAnalysisResult, SceneRecord
from api.services.intel.omega_client import submodule_sha


def analyze_video_stub(upload_id: str, source_uri: str) -> SceneAnalysisResult:
    """Local stub for dev/tests. Real impl lives in workers/scene_analysis_worker.py."""
    sha = submodule_sha() or "unknown"
    return SceneAnalysisResult(
        upload_id=upload_id,
        intel_submodule_sha=sha,
        scenes=[
            SceneRecord(
                t_start=0.0,
                t_end=12.0,
                kind="stub_scene",
                signals={"note": "stub adapter; not real OmegaClips output"},
            )
        ],
    )
