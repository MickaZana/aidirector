"""Clip ranking worker.

Wraps OmegaClips ranking pipeline (capability_map #11, #21, #23). Reads
persisted scenes for a job, calls candidate_clip_selection +
candidate_reel_ranking, writes ClipCandidate rows.

Phase 0 status: stub.
"""
from __future__ import annotations

import modal

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=4096)
def rank_clip_candidates(job_id: str, tenant_slug: str) -> dict[str, object]:
    """Phase 0 stub. Phase 1 implementation imports OmegaClips ranking modules."""
    raise NotImplementedError("Phase 1 — wraps football_pipeline.candidate_reel_ranking")
