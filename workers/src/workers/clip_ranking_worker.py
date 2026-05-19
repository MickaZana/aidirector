"""Clip ranking worker — Modal-side wrapper over the ranking adapter.

This file is allowed to import OmegaClips indirectly via the adapter. It
should NOT contain ranking business logic — the boundary is the adapter at
`apps/api/src/api/services/intel/clip_ranking_adapter.py`.

Entrypoints:
  - `rank_clip_candidates_fixture(upload_id, scenes_serialized)` — phase 3
    path. Takes JSON-serialised SceneRecord list (same shape AI Director
    persists in `scenes.signals`), calls the adapter, returns ranked output
    as JSON. Useful for local probes and CI smoke tests; no video needed.
  - `rank_clip_candidates(job_id, tenant_slug)` — full-video phase. Stub
    until R2 + the analyzer worker are wired together end-to-end.
"""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def rank_clip_candidates_fixture(
    upload_id: str, scenes_serialized: list[dict]
) -> dict:
    """Run real OmegaClips ranking over already-persisted scenes.

    Returns the raw RankedClipCandidates as a dict so the dispatcher can
    persist it on the AI Director side.
    """
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates

    scenes = [SceneRecord.model_validate(s) for s in scenes_serialized]
    ranked = rank_clip_candidates(upload_id, scenes)
    return ranked.model_dump(mode="json")


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=4096)
def rank_clip_candidates(job_id: str, tenant_slug: str) -> dict:
    """Phase 3 stub. Phase 3.5 will read persisted scenes from Postgres,
    call the adapter, and write ranked candidates back."""
    raise NotImplementedError(
        "Phase 3.5 — read scenes from DB, run ranking, persist candidates."
    )
