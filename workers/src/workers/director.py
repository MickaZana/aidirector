"""Director Agent worker — wraps OmegaClips' claude_intelligence with strict schema.

OmegaClips' `claude_intelligence.generate_segment_render_plan()` returns a dict.
This worker validates that output against the AI Director `DirectorPlan` schema
before persisting. The prompt is prompt-cached at the Anthropic API to drive
cost down by ~80%.
"""
from __future__ import annotations

from workers.contracts import DirectorPlan
from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def direct_render_plan(job_id: str, model: str = "claude-sonnet-4-6") -> dict:
    """Stub — to be implemented in Phase 1.

    Steps:
      1. Load scenes for job_id from Postgres.
      2. Build prompt: system (cached) + scenes + transcript.
      3. Call Anthropic Messages API with response_format pinned to JSON.
      4. Parse + validate against `DirectorPlan`.
      5. Persist to `director_plans` table; return the plan id.
    """
    raise NotImplementedError("Phase 1 — see plan §6 + §9")
