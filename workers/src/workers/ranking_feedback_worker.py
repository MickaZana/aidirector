"""Ranking Feedback Worker — Modal-side wrapper over the controlled-feedback path.

Zero math, zero feedback policy. Receives a job_id + a mapping of
{scene_index → PerformanceFeatureView dict}, re-runs the ranking adapter
with the feedback enabled, persists one RankingSnapshot per ranked
candidate. The capping, the confidence gating, the explainability all
live in `ranking_feedback_adapter.apply_feedback_to_rank_score`.

Phase 8 entrypoint: `apply_ranking_feedback_fixture`.
Phase 8.5 entrypoint: `apply_ranking_feedback_for_job` (stub).
"""

from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def apply_ranking_feedback_fixture(
    job_id: str,
    prior_performance_serialised: dict,
) -> dict:
    """Apply controlled engagement feedback to a job's candidates.

    `prior_performance_serialised` is a dict keyed by stringified
    scene_index → dict containing the PerformanceFeatureView fields the
    feedback adapter needs (engagement_score, engagement_confidence,
    maturity_state, feature_version).
    """
    import uuid as _uuid

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import ClipCandidate, Job, MaturityState, Scene
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.intel.ranking_feedback_adapter import PerformanceFeatureView
    from api.services.ranking_snapshot_persistence import persist_ranking_snapshot

    assert engine is not None, "DATABASE_URL must be set for ranking feedback worker"

    with Session(engine) as db:
        job = db.execute(select(Job).where(Job.id == _uuid.UUID(job_id))).scalar_one()
        scene_rows = db.execute(select(Scene).where(Scene.job_id == job.id)).scalars().all()
        candidate_rows = (
            db.execute(select(ClipCandidate).where(ClipCandidate.job_id == job.id)).scalars().all()
        )

        prior: dict[int, PerformanceFeatureView] = {}
        for k, payload in prior_performance_serialised.items():
            prior[int(k)] = PerformanceFeatureView(
                export_id=_uuid.UUID(payload["export_id"]),
                tenant_id=_uuid.UUID(payload["tenant_id"]),
                feature_version=payload.get("feature_version", "v1"),
                maturity_state=MaturityState(payload["maturity_state"]),
                engagement_confidence=float(payload["engagement_confidence"]),
                normalized_view_rate=payload.get("normalized_view_rate"),
                normalized_completion_rate=payload.get("normalized_completion_rate"),
                normalized_watch_time=payload.get("normalized_watch_time"),
                replay_rate=payload.get("replay_rate"),
                share_rate=payload.get("share_rate"),
                engagement_score=float(payload["engagement_score"]),
                experiment_group_id=(
                    _uuid.UUID(payload["experiment_group_id"])
                    if payload.get("experiment_group_id")
                    else None
                ),
            )

        ranked = rank_clip_candidates(
            upload_id=str(job.upload_id),
            scenes=[
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
            ],
            prior_performance=prior,
        )

        # Snapshot each candidate. Map back from scene_index → candidate row.
        by_scene_index = {i: c for i, c in enumerate(candidate_rows)}
        snapshots = []
        for cand_record in ranked.candidates:
            target = by_scene_index.get(cand_record.scene_index or 0)
            if target is None:
                continue
            snap = persist_ranking_snapshot(
                db,
                job=job,
                candidate=target,
                scores=cand_record.scores,
            )
            snapshots.append(
                {
                    "id": str(snap.id),
                    "candidate_id": str(snap.candidate_id),
                    "base_rank_score": snap.base_rank_score,
                    "engagement_adjustment": snap.engagement_adjustment,
                    "final_rank_score": snap.final_rank_score,
                    "feedback_applied": snap.feedback_applied,
                }
            )
        db.commit()
        return {"snapshots": snapshots, "ranked_count": len(ranked.candidates)}


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def apply_ranking_feedback_for_job(job_id: str, tenant_slug: str) -> dict:
    """Read PerformanceFeatureViews from DB, apply controlled feedback,
    persist snapshots.

    Pipeline:
      1. Load scenes + candidates for the job from DB.
      2. For each export linked to this job, load PerformanceFeatureView.
      3. Re-run ranking with prior_performance feedback enabled.
      4. Persist one RankingSnapshot per candidate.
      5. Return snapshot summary.
    """
    import uuid as _uuid
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import (
        ClipCandidate,
        ExportArtifact,
        Job,
        PerformanceFeatureSet,
        RenderJob,
        RenderOutput,
        Scene,
    )
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates as _rank
    from api.services.intel.ranking_feedback_adapter import PerformanceFeatureView
    from api.services.ranking_snapshot_persistence import persist_ranking_snapshot

    assert engine is not None, "DATABASE_URL must be set for ranking feedback worker"

    log = __import__("logging").getLogger(__name__)
    log.info("apply_ranking_feedback_for_job: job=%s tenant=%s", job_id, tenant_slug)

    with Session(engine) as db:
        job = db.execute(select(Job).where(Job.id == _uuid.UUID(job_id))).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        scene_rows = (
            db.execute(select(Scene).where(Scene.job_id == job.id).order_by(Scene.t_start))
            .scalars()
            .all()
        )

        candidate_rows = (
            db.execute(
                select(ClipCandidate)
                .where(ClipCandidate.job_id == job.id)
                .order_by(ClipCandidate.confidence_score.desc().nullslast())
            )
            .scalars()
            .all()
        )

        if not scene_rows or not candidate_rows:
            log.warning(
                "apply_ranking_feedback_for_job: no scenes/candidates for job %s",
                job_id,
            )
            return {
                "job_id": job_id,
                "status": "skipped",
                "reason": "no scenes or candidates",
            }

        # Build PerformanceFeatureView map from ExportArtifacts linked to this job
        prior_performance: dict[int, PerformanceFeatureView] = {}
        render_job_ids = (
            db.execute(select(RenderJob.id).where(RenderJob.job_id == job.id)).scalars().all()
        )
        if render_job_ids:
            render_outputs = (
                db.execute(
                    select(RenderOutput).where(RenderOutput.render_job_id.in_(render_job_ids))
                )
                .scalars()
                .all()
            )
            if render_outputs:
                render_output_ids = [ro.id for ro in render_outputs]
                artifacts = (
                    db.execute(
                        select(ExportArtifact).where(
                            ExportArtifact.render_output_id.in_(render_output_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                for artifact in artifacts:
                    feature_set = db.execute(
                        select(PerformanceFeatureSet).where(
                            PerformanceFeatureSet.export_id == artifact.id
                        )
                    ).scalar_one_or_none()
                    if feature_set is not None:
                        view = PerformanceFeatureView(
                            export_id=artifact.id,
                            tenant_id=artifact.tenant_id,
                            feature_version=feature_set.feature_version,
                            maturity_state=_maturity_state(feature_set.maturity_state),
                            engagement_confidence=feature_set.engagement_confidence,
                            normalized_view_rate=feature_set.normalized_view_rate,
                            normalized_completion_rate=feature_set.normalized_completion_rate,
                            normalized_watch_time=feature_set.normalized_watch_time,
                            replay_rate=feature_set.replay_rate,
                            share_rate=feature_set.share_rate,
                            engagement_score=feature_set.engagement_score,
                            experiment_group_id=feature_set.experiment_group_id,
                        )
                        # Map by scene_index derived from the ExportArtifact's
                        # associated candidate position. Each export maps to
                        # exactly one scene_index via its render_output → candidate.
                        scene_index = _resolve_scene_index(db, artifact, candidate_rows) or 0
                        prior_performance[scene_index] = view

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

        # Re-rank with feedback enabled
        ranked = _rank(
            str(job.upload_id),
            scenes,
            prior_performance=prior_performance if prior_performance else None,
        )

        # Persist snapshots
        by_scene_index = {i: c for i, c in enumerate(candidate_rows)}
        snapshots = []
        for cand_record in ranked.candidates:
            target = by_scene_index.get(cand_record.scene_index or 0)
            if target is None:
                continue
            snap = persist_ranking_snapshot(
                db, job=job, candidate=target, scores=cand_record.scores
            )
            snapshots.append(
                {
                    "id": str(snap.id),
                    "candidate_id": str(snap.candidate_id),
                    "base_rank_score": snap.base_rank_score,
                    "engagement_adjustment": snap.engagement_adjustment,
                    "final_rank_score": snap.final_rank_score,
                    "feedback_applied": snap.feedback_applied,
                }
            )

        db.commit()
        log.info(
            "apply_ranking_feedback_for_job: job=%s snapshots=%d",
            job_id,
            len(snapshots),
        )
        return {
            "job_id": job_id,
            "status": "complete",
            "snapshots": snapshots,
            "ranked_count": len(ranked.candidates),
        }


def _maturity_state(value: str):
    """Import MaturityState lazily to avoid circular imports at module level."""
    from api.models import MaturityState

    return MaturityState(value)


def _resolve_scene_index(db, artifact, candidate_rows) -> int | None:
    """Resolve which scene_index an ExportArtifact maps to by walking
    ExportArtifact → RenderOutput → RenderJob → ClipCandidate relationship.
    Falls back to 0 if the chain cannot be resolved."""
    from sqlalchemy import select

    from api.models import ClipCandidate, RenderJob, RenderOutput

    render_output = db.execute(
        select(RenderOutput).where(RenderOutput.id == artifact.render_output_id)
    ).scalar_one_or_none()
    if render_output is None:
        return None

    render_job = db.execute(
        select(RenderJob).where(RenderJob.id == render_output.render_job_id)
    ).scalar_one_or_none()
    if render_job is None:
        return None

    # Find the candidate that matches this render_job's candidate_id
    for i, c in enumerate(candidate_rows):
        if str(c.id) == render_job.candidate_id:
            return i

    return None
