"""Scene analysis worker — Modal-side wrapper over the adapter.

This file is allowed to import OmegaClips indirectly via the adapter. It
should NOT contain OmegaClips business logic — the boundary is the adapter
at `apps/api/src/api/services/intel/scene_analysis_adapter.py`.

Two entrypoints:
  - `analyze_video_fixture`: runs the phase-2 OmegaClips integration path
    (scoreboard change tracking over a synthetic OCR fixture). Useful for
    local probes and CI smoke tests; does NOT require a video file.
  - `analyze_video`: phase-3 entrypoint that will download R2 source, run
    the full orchestrator, and write scenes back. Stub for now.
"""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=120, memory=2048)
def analyze_video_fixture(upload_id: str, fixture_reads: list[dict]) -> dict:
    """Runs the real OmegaClips ScoreboardChangeTracker path over a fixture sequence.

    Returns the raw SceneAnalysisResult as a dict so the dispatcher can
    persist it on the AI Director side without round-tripping pydantic
    across the Modal boundary.
    """
    from api.services.intel.scene_analysis_adapter import analyze_video

    result = analyze_video(
        upload_id=upload_id,
        source_uri="fixture://memory",
        fixture_reads=fixture_reads,
    )
    return result.model_dump(mode="json")


@app.function(image=intel_image, secrets=secrets, timeout=1800, memory=8192)
def analyze_video(job_id: str, upload_r2_key: str, tenant_slug: str) -> dict:
    """Phase 3: full-video orchestrator. Stub until R2 + orchestrator wired."""
    raise NotImplementedError(
        "Phase 3 — full FootballPipelineOrchestrator integration. "
        "Use analyze_video_fixture for the phase-2 integration probe."
    )
