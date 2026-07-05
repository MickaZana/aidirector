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
    """Read clip_candidates from Postgres, build DirectorPlan, persist.

    Pipeline:
      1. Load ClipCandidate rows for the job from DB (ordered by confidence desc).
      2. Call director_plan_builder.build_director_plan() with the candidates.
      3. Optionally enrich via director_agent_adapter (if enabled).
      4. Persist via director_plan_persistence.
      5. Enqueue the render worker (q:render-cpu) for the next stage.
      6. Return the plan summary.
    """
    import uuid as _uuid
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import ClipCandidate, Job, Upload
    from api.services.director_plan_builder import build_director_plan as _build
    from api.services.director_plan_persistence import persist_director_plan
    from api.services.intel.director_agent_adapter import enrich_director_plan
    from api.services.queue import queue_for

    assert engine is not None, "DATABASE_URL must be set for director worker"

    log = __import__("logging").getLogger(__name__)
    log.info("build_director_plan: job=%s tenant=%s", job_id, tenant_slug)

    with Session(engine) as db:
        job = db.execute(select(Job).where(Job.id == _uuid.UUID(job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        candidate_rows = (
            db.execute(
                select(ClipCandidate)
                .where(ClipCandidate.job_id == job.id)
                .order_by(ClipCandidate.confidence_score.desc().nullslast())
            )
            .scalars()
            .all()
        )

        if not candidate_rows:
            log.warning("build_director_plan: no candidates for job %s", job_id)
            return {"job_id": job_id, "status": "skipped", "reason": "no candidates"}

        # Build the deterministic DirectorPlan
        plan = _build(
            upload_id=str(job.upload_id),
            job_id=job_id,
            candidates=candidate_rows,
            platform_targets=["youtube_shorts", "tiktok", "instagram_reels"],
        )

        # Optionally enrich via Claude (disabled by default; enable via config)
        from api.config import get_settings

        settings = get_settings()
        enrichment_enabled = getattr(settings, "llm_enrichment_enabled", False)
        if enrichment_enabled and settings.anthropic_api_key:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            def _enricher(request: dict) -> dict:
                msg = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=2048,
                    messages=[{"role": "user", "content": str(request)}],
                )
                import json

                # Iterate over content blocks to handle both TextBlock and ThinkingBlock
                _text = ""
                for _block in msg.content:
                    if hasattr(_block, "text"):
                        _text = _block.text
                        break
                if not _text:
                    _text = msg.content[0].text
                start = _text.find("{")
                end = _text.rfind("}") + 1
                return json.loads(_text[start:end]) if start >= 0 else {}

            plan = enrich_director_plan(plan, enabled=True, enricher_fn=_enricher)

        # Persist the plan
        row = persist_director_plan(db, job=job, plan=plan)
        db.commit()

        # Look up the Upload to get the actual R2 key for source_uri
        upload = db.execute(select(Upload).where(Upload.id == job.upload_id)).scalar_one_or_none()
        source_uri = upload.r2_key if upload else str(job.upload_id)

        # Enqueue render for each variant in the plan
        for candidate in plan.selected_candidates:
            queue_for("render-cpu").enqueue(
                "workers.render_worker.execute_render_job",
                {
                    "job_id": job_id,
                    "source_uri": source_uri,
                },
                job_timeout=600,
                result_ttl=86400,
            )

        log.info(
            "build_director_plan: job=%s plan=%s candidates=%d variants=%d",
            job_id,
            row.id,
            len(plan.selected_candidates),
            sum(len(c.variants) for c in plan.selected_candidates),
        )
        return {
            "job_id": job_id,
            "status": "complete",
            "plan_id": str(row.id),
            "candidates_selected": len(plan.selected_candidates),
            "total_variants": sum(len(c.variants) for c in plan.selected_candidates),
            "cost_estimate_cents": plan.cost_estimate_cents,
        }
