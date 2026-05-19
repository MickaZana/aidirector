"""Director worker — Modal-side wrapper over the deterministic builder.

This file is the second-most-sensitive boundary in the system (after the
two intel adapters). It contains NO planning logic — the deterministic
builder at `api.services.director_plan_builder` is the authority. The
worker only:
  1. Loads inputs (candidate IDs + platform targets + job context)
  2. Calls the builder
  3. Optionally calls the sandboxed Claude enrichment adapter
  4. Persists via the persistence service

Entrypoints:
  - `build_director_plan_fixture(job_id, candidate_ids_serialized,
    platform_targets, enable_enrichment)` — phase 4 path
  - `build_director_plan(job_id, tenant_slug)` — phase 4.5 stub
"""
from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=180, memory=2048)
def build_director_plan_fixture(
    upload_id: str,
    job_id: str,
    candidate_payloads: list[dict],
    platform_targets: list[str],
    enable_enrichment: bool = False,
) -> dict:
    """Deterministic plan build over precomputed candidate payloads.

    The caller passes a list of dicts representing each candidate (id,
    t_start, t_end, confidence_score, quality_score, platform_score,
    rationale, scores). We rebuild minimal ORM-shaped objects locally and
    hand them to the builder.
    """
    from types import SimpleNamespace

    from api.schemas.director_plan import DirectorPlan
    from api.services.director_plan_builder import build_director_plan
    from api.services.intel.director_agent_adapter import enrich_director_plan

    namespaced = [SimpleNamespace(**c) for c in candidate_payloads]
    plan = build_director_plan(
        upload_id=upload_id,
        job_id=job_id,
        candidates=namespaced,
        platform_targets=platform_targets,  # type: ignore[arg-type]
    )
    plan = enrich_director_plan(plan, enabled=enable_enrichment, enricher_fn=None)
    # Re-validate before returning so the dispatcher receives a guaranteed-
    # contract-conformant payload.
    validated = DirectorPlan.model_validate(plan.model_dump(mode="python"))
    return validated.model_dump(mode="json")


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=4096)
def build_director_plan(job_id: str, tenant_slug: str) -> dict:
    """Phase 4.5: read candidates from Postgres, build, optionally enrich,
    persist. Stub until the Postgres reader path is wired."""
    raise NotImplementedError(
        "Phase 4.5 — read clip_candidates from DB, run builder + persistence."
    )
