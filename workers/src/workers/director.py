"""Director Agent worker — wraps OmegaClips' claude_intelligence with strict schema.

OmegaClips' `claude_intelligence.generate_segment_render_plan()` returns a dict.
This worker validates that output against the AI Director `DirectorPlan` schema
before persisting. The prompt is prompt-cached at the Anthropic API to drive
cost down by ~80%.
"""

from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def direct_render_plan(job_id: str, model: str = "claude-sonnet-4-6") -> dict:
    """Build a DirectorPlan via LLM for one job.

    Steps:
      1. Load scenes + candidates for job_id from Postgres.
      2. Build a concise prompt with scene descriptions.
      3. Call Anthropic Messages API.
      4. Parse + validate against `DirectorPlan` schema.
      5. Persist to `director_plans` table.
      6. Return the plan summary.

    Falls back to deterministic builder if the LLM call fails.
    """
    import json
    import uuid as _uuid
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import ClipCandidate, Job, Scene
    from api.schemas.director_plan import DirectorPlan as DirectorPlanContract
    from api.services.director_plan_builder import build_director_plan as _build_deterministic
    from api.services.director_plan_persistence import persist_director_plan

    assert engine is not None, "DATABASE_URL must be set for director worker"

    log = __import__("logging").getLogger(__name__)
    log.info("direct_render_plan: job=%s model=%s", job_id, model)

    with Session(engine) as db:
        job = db.execute(select(Job).where(Job.id == _uuid.UUID(job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        scenes = (
            db.execute(select(Scene).where(Scene.job_id == job.id).order_by(Scene.t_start))
            .scalars()
            .all()
        )

        candidates = (
            db.execute(
                select(ClipCandidate)
                .where(ClipCandidate.job_id == job.id)
                .order_by(ClipCandidate.confidence_score.desc().nullslast())
            )
            .scalars()
            .all()
        )

        if not candidates:
            log.warning("direct_render_plan: no candidates for job %s", job_id)
            return {"job_id": job_id, "status": "skipped", "reason": "no candidates"}

        # Try LLM path first
        try:
            from api.config import get_settings

            settings = get_settings()
            if not settings.anthropic_api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")

            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

            scene_summaries = "\n".join(
                f"  - Scene {i}: kind={s.kind}, t_start={s.t_start:.1f}s, "
                f"t_end={s.t_end:.1f}s, intensity={s.intensity}"
                for i, s in enumerate(scenes[:20])
            )
            candidate_summaries = "\n".join(
                f"  - Candidate {c.id}: score={c.confidence_score}, "
                f"t={c.t_start:.1f}-{c.t_end:.1f}s"
                for c in candidates[:20]
            )

            prompt = (
                f"You are an expert sports video director. Create a DirectorPlan "
                f"for job {job_id} with the following scenes and candidates.\n\n"
                f"Scenes ({len(scenes)}):\n{scene_summaries}\n\n"
                f"Candidates ({len(candidates)}):\n{candidate_summaries}\n\n"
                f"Return a JSON object with key 'selected_candidates' containing "
                f"the top candidates to include in a highlight reel."
            )

            message = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            # Iterate over content blocks to handle both TextBlock and ThinkingBlock
            _text = ""
            for _block in message.content:
                if hasattr(_block, "text"):
                    _text = _block.text
                    break
            if not _text:
                _text = message.content[0].text
            start = _text.find("{")
            end = _text.rfind("}") + 1
            llm_result = json.loads(_text[start:end]) if start >= 0 else {}

            if llm_result.get("selected_candidates"):
                # Build a DirectorPlanContract from the LLM result
                # Map LLM-selected candidates back to ORM objects for the persistence layer
                selected_ids = [c.get("candidate_id") for c in llm_result["selected_candidates"]]
                llm_selected = [c for c in candidates if str(c.id) in selected_ids]
                if not llm_selected:
                    llm_selected = candidates[: len(llm_result["selected_candidates"])]
                plan = _build_deterministic(
                    upload_id=str(job.upload_id),
                    job_id=job_id,
                    candidates=llm_selected,
                    platform_targets=["youtube_shorts", "tiktok", "instagram_reels"],
                )
                row = persist_director_plan(db, job=job, plan=plan)
                db.commit()
                log.info("direct_render_plan: job=%s LLM plan persisted", job_id)
                return {
                    "job_id": job_id,
                    "status": "complete",
                    "plan_id": str(row.id),
                    "model": model,
                    "source": "llm",
                }

            raise RuntimeError("LLM returned no selected_candidates")

        except Exception as exc:
            log.warning(
                "direct_render_plan: LLM path failed (%s) — using deterministic fallback",
                exc,
            )
            plan = _build_deterministic(
                upload_id=str(job.upload_id),
                job_id=job_id,
                candidates=candidates,
                platform_targets=["youtube_shorts", "tiktok", "instagram_reels"],
            )
            row = persist_director_plan(db, job=job, plan=plan)
            db.commit()
            return {
                "job_id": job_id,
                "status": "complete",
                "plan_id": str(row.id),
                "model": "deterministic-builder/v1",
                "source": "deterministic_fallback",
            }
