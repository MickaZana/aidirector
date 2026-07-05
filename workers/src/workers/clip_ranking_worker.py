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
def rank_clip_candidates_fixture(upload_id: str, scenes_serialized: list[dict]) -> dict:
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
    """Read persisted scenes from Postgres, run ranking adapter, persist.

    Pipeline:
      1. Load scenes for the job from DB (ordered by t_start).
      2. Convert to SceneRecord list.
      3. Call clip_ranking_adapter.rank_clip_candidates().
      4. Persist ranked candidates via clip_candidate_persistence.
      5. Enqueue the director worker (q:llm) for the next stage.
      6. Return the ranked result summary.
    """
    import uuid as _uuid
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import Job, Scene
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates as _rank
    from api.services.clip_candidate_persistence import persist_clip_candidates
    from api.services.queue import queue_for

    assert engine is not None, "DATABASE_URL must be set for clip ranking worker"

    log = __import__("logging").getLogger(__name__)
    log.info("rank_clip_candidates: job=%s tenant=%s", job_id, tenant_slug)

    with Session(engine) as db:
        job = db.execute(select(Job).where(Job.id == _uuid.UUID(job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        scene_rows = (
            db.execute(select(Scene).where(Scene.job_id == job.id).order_by(Scene.t_start))
            .scalars()
            .all()
        )

        if not scene_rows:
            log.warning("rank_clip_candidates: no scenes found for job %s", job_id)
            return {"job_id": job_id, "status": "skipped", "reason": "no scenes"}

        scenes = [
            SceneRecord(
                t_start=s.t_start,
                t_end=s.t_end,
                kind=s.kind,
                arc_position=s.arc_position,
                intensity=s.intensity,
                importance=s.importance,
                signals=s.signals,
            )
            for s in scene_rows
        ]

        ranked = _rank(str(job.upload_id), scenes)
        persist_clip_candidates(db, job=job, scenes_in_order=scene_rows, ranked=ranked)
        db.commit()

        # Enqueue the director worker for the next pipeline stage
        queue_for("llm").enqueue(
            "workers.director_worker.build_director_plan",
            {"job_id": job_id, "tenant_slug": tenant_slug},
            job_timeout=600,
            result_ttl=86400,
        )

        log.info(
            "rank_clip_candidates: job=%s ranked %d candidates",
            job_id,
            len(ranked.candidates),
        )
        return {
            "job_id": job_id,
            "status": "complete",
            "candidates_ranked": len(ranked.candidates),
        }
