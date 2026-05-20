"""Assemble the JobView composite response.

One function (`build_job_view`) and one polling helper (`build_job_events`).
Both are READ-ONLY: they execute SELECTs through the session, never
mutate.

Tenant scoping is enforced on every query — the caller hands us a
Tenant and a job_id; we never load a Job by id alone.

The assembler is intentionally a service, not a router helper, so the
exact same shape can be returned by:
  - GET /api/jobs/{id}/view (the user-facing endpoint)
  - the dev fixture-export tool (when refreshing fixtures from real DB)
  - tests / probes
"""
from __future__ import annotations

import uuid
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from api.models import (
    ClipCandidate,
    DirectorPlan,
    ExportArtifact,
    Job,
    PerformanceFeatureSet,
    RankingSnapshot,
    RenderJob,
    RenderOutput,
    Scene,
    Tenant,
    Upload,
    UsageEvent,
)
from api.schemas.director_plan import DirectorPlan as DirectorPlanContract
from api.schemas.job_view import (
    ClipCandidateView,
    ExportArtifactView,
    JobEventsView,
    JobRowView,
    JobView,
    PerformanceFeatureViewRow,
    RankingSnapshotView,
    RenderJobView,
    RenderOutputView,
    SceneView,
    UploadView,
    UsageEventView,
)


def build_job_view(
    db: Session,
    *,
    tenant: Tenant,
    job_id: uuid.UUID,
) -> JobView | None:
    """Return the full composite view, or None if the job doesn't belong to this tenant."""
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        return None

    upload = db.execute(
        select(Upload).where(Upload.id == job.upload_id, Upload.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if upload is None:
        # Pipeline invariant: every job has an upload. If this row is missing,
        # the data store is in an unrecoverable state for this job — fail loudly.
        raise RuntimeError(
            f"job {job.id} references upload {job.upload_id} that does not exist for tenant {tenant.id}"
        )

    scenes = db.execute(
        select(Scene)
        .where(Scene.job_id == job.id, Scene.tenant_id == tenant.id)
        .order_by(Scene.t_start)
    ).scalars().all()

    candidates = db.execute(
        select(ClipCandidate)
        .where(ClipCandidate.job_id == job.id, ClipCandidate.tenant_id == tenant.id)
        .order_by(ClipCandidate.t_start)
    ).scalars().all()
    candidate_ids = [c.id for c in candidates]

    plan_row = db.execute(
        select(DirectorPlan)
        .where(DirectorPlan.job_id == job.id, DirectorPlan.tenant_id == tenant.id)
        .order_by(desc(DirectorPlan.created_at))
        .limit(1)
    ).scalar_one_or_none()
    director_plan_contract: DirectorPlanContract | None = (
        DirectorPlanContract.model_validate(plan_row.plan_json) if plan_row else None
    )

    render_jobs = db.execute(
        select(RenderJob)
        .where(RenderJob.job_id == job.id, RenderJob.tenant_id == tenant.id)
        .order_by(RenderJob.created_at)
    ).scalars().all()
    render_job_ids = [rj.id for rj in render_jobs]

    render_outputs = (
        db.execute(
            select(RenderOutput)
            .where(
                RenderOutput.tenant_id == tenant.id,
                RenderOutput.render_job_id.in_(render_job_ids),
            )
            .order_by(RenderOutput.created_at)
        ).scalars().all()
        if render_job_ids
        else []
    )
    render_output_ids = [ro.id for ro in render_outputs]

    exports = (
        db.execute(
            select(ExportArtifact)
            .where(
                ExportArtifact.tenant_id == tenant.id,
                ExportArtifact.render_output_id.in_(render_output_ids),
            )
            .order_by(ExportArtifact.created_at)
        ).scalars().all()
        if render_output_ids
        else []
    )
    export_ids = [e.id for e in exports]

    feature_views = (
        db.execute(
            select(PerformanceFeatureSet)
            .where(
                PerformanceFeatureSet.tenant_id == tenant.id,
                PerformanceFeatureSet.export_id.in_(export_ids),
            )
            .order_by(desc(PerformanceFeatureSet.evaluated_at))
        ).scalars().all()
        if export_ids
        else []
    )

    snapshots = (
        db.execute(
            select(RankingSnapshot)
            .where(
                RankingSnapshot.tenant_id == tenant.id,
                RankingSnapshot.job_id == job.id,
            )
            .order_by(desc(RankingSnapshot.created_at))
        ).scalars().all()
    )

    usage_events = db.execute(
        select(UsageEvent)
        .where(UsageEvent.tenant_id == tenant.id, UsageEvent.job_id == job.id)
        .order_by(UsageEvent.created_at)
    ).scalars().all()

    return JobView(
        job=_job_view(job),
        upload=_upload_view(upload),
        scenes=[_scene_view(s) for s in scenes],
        candidates=[_candidate_view(c) for c in candidates],
        director_plan=director_plan_contract,
        render_jobs=[_render_job_view(rj) for rj in render_jobs],
        render_outputs=[_render_output_view(ro) for ro in render_outputs],
        exports=[_export_view(e) for e in exports],
        feature_views=[_feature_view(f) for f in feature_views],
        snapshots=[_snapshot_view(s) for s in snapshots],
        usage_events=[_usage_view(u) for u in usage_events],
    )


def build_job_events(
    db: Session,
    *,
    tenant: Tenant,
    job_id: uuid.UUID,
) -> JobEventsView | None:
    """Cheap status refresh for the polling transport.

    Returns just the bits the client needs to decide whether to refetch
    the full JobView: status, a monotonic revision number (one per
    usage_event row), and the latest usage_event marker.
    """
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        return None

    latest = db.execute(
        select(UsageEvent.created_at, UsageEvent.event_type)
        .where(UsageEvent.tenant_id == tenant.id, UsageEvent.job_id == job.id)
        .order_by(desc(UsageEvent.created_at))
        .limit(1)
    ).first()

    counts = _counts_for_job(db, tenant_id=tenant.id, job=job)

    revision = counts.get("usage_events", 0)

    return JobEventsView(
        job_id=str(job.id),
        status=job.status,
        revision=revision,
        last_event_at=latest[0].isoformat() if latest else None,
        last_event_type=latest[1] if latest else None,
        counts=counts,
    )


# --- internal helpers -----------------------------------------------------


def _counts_for_job(db: Session, *, tenant_id: uuid.UUID, job: Job) -> dict[str, int]:
    def _count(stmt) -> int:
        return int(db.execute(stmt).scalar_one() or 0)

    scenes = _count(
        select(func.count(Scene.id)).where(Scene.job_id == job.id, Scene.tenant_id == tenant_id)
    )
    candidates = _count(
        select(func.count(ClipCandidate.id)).where(
            ClipCandidate.job_id == job.id, ClipCandidate.tenant_id == tenant_id
        )
    )
    render_jobs = _count(
        select(func.count(RenderJob.id)).where(
            RenderJob.job_id == job.id, RenderJob.tenant_id == tenant_id
        )
    )
    render_outputs = _count(
        select(func.count(RenderOutput.id))
        .join(RenderJob, RenderJob.id == RenderOutput.render_job_id)
        .where(RenderJob.job_id == job.id, RenderJob.tenant_id == tenant_id)
    )
    exports = _count(
        select(func.count(ExportArtifact.id))
        .join(RenderOutput, RenderOutput.id == ExportArtifact.render_output_id)
        .join(RenderJob, RenderJob.id == RenderOutput.render_job_id)
        .where(RenderJob.job_id == job.id, ExportArtifact.tenant_id == tenant_id)
    )
    feature_views = _count(
        select(func.count(PerformanceFeatureSet.id))
        .join(ExportArtifact, ExportArtifact.id == PerformanceFeatureSet.export_id)
        .join(RenderOutput, RenderOutput.id == ExportArtifact.render_output_id)
        .join(RenderJob, RenderJob.id == RenderOutput.render_job_id)
        .where(RenderJob.job_id == job.id, PerformanceFeatureSet.tenant_id == tenant_id)
    )
    snapshots = _count(
        select(func.count(RankingSnapshot.id)).where(
            RankingSnapshot.job_id == job.id, RankingSnapshot.tenant_id == tenant_id
        )
    )
    usage_events = _count(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.job_id == job.id, UsageEvent.tenant_id == tenant_id
        )
    )

    return {
        "scenes": scenes,
        "candidates": candidates,
        "render_jobs": render_jobs,
        "render_outputs": render_outputs,
        "exports": exports,
        "feature_views": feature_views,
        "snapshots": snapshots,
        "usage_events": usage_events,
    }


def _job_view(j: Job) -> JobRowView:
    return JobRowView(
        id=str(j.id),
        tenant_id=str(j.tenant_id),
        upload_id=str(j.upload_id),
        intent=j.intent,
        status=j.status,
        intel_submodule_sha=j.intel_submodule_sha,
        error=j.error,
        cost_budget_cents=j.cost_budget_cents,
        cost_actual_cents=j.cost_actual_cents,
        created_at=j.created_at.isoformat(),
    )


def _upload_view(u: Upload) -> UploadView:
    return UploadView(
        id=str(u.id),
        tenant_id=str(u.tenant_id),
        filename=u.filename,
        r2_key=u.r2_key,
        bytes=u.bytes,
        duration_s=u.duration_s,
        sport=u.sport,
        status=u.status,
        created_at=u.created_at.isoformat(),
    )


def _scene_view(s: Scene) -> SceneView:
    return SceneView(
        id=str(s.id),
        job_id=str(s.job_id),
        tenant_id=str(s.tenant_id),
        t_start=s.t_start,
        t_end=s.t_end,
        kind=s.kind,
        arc_position=s.arc_position,
        intensity=s.intensity,
        importance=s.importance,
        signals=s.signals or {},
    )


def _candidate_view(c: ClipCandidate) -> ClipCandidateView:
    return ClipCandidateView(
        id=str(c.id),
        job_id=str(c.job_id),
        tenant_id=str(c.tenant_id),
        scene_id=str(c.scene_id) if c.scene_id else None,
        t_start=c.t_start,
        t_end=c.t_end,
        confidence_score=c.confidence_score,
        quality_score=c.quality_score,
        platform_score=c.platform_score,
        rationale=c.rationale,
        scores=c.scores or {},
    )


def _render_job_view(rj: RenderJob) -> RenderJobView:
    return RenderJobView(
        id=str(rj.id),
        job_id=str(rj.job_id),
        tenant_id=str(rj.tenant_id),
        candidate_id=str(rj.candidate_id),
        pipeline=rj.pipeline,
        platform=rj.platform,
        status=rj.status,
        settings=rj.settings or {},
        error=rj.error,
        finished_at=rj.finished_at.isoformat() if rj.finished_at else None,
        cost_cents=rj.cost_cents,
        created_at=rj.created_at.isoformat(),
    )


def _render_output_view(ro: RenderOutput) -> RenderOutputView:
    return RenderOutputView(
        id=str(ro.id),
        render_job_id=str(ro.render_job_id),
        tenant_id=str(ro.tenant_id),
        r2_key=ro.r2_key,
        aspect_ratio=ro.aspect_ratio,
        duration_s=ro.duration_s,
        bytes=ro.bytes,
        output_metadata=ro.output_metadata or {},
    )


def _export_view(e: ExportArtifact) -> ExportArtifactView:
    return ExportArtifactView(
        id=str(e.id),
        tenant_id=str(e.tenant_id),
        render_output_id=str(e.render_output_id),
        platform=e.platform,
        export_status=e.export_status,
        export_version=e.export_version,
        export_hash=e.export_hash,
        content_hash=e.content_hash,
        content_bytes=e.content_bytes,
        filename=e.filename,
        storage_uri=e.storage_uri,
        artifact_metadata=e.artifact_metadata or {},
        published_at=e.published_at.isoformat() if e.published_at else None,
        created_at=e.created_at.isoformat(),
    )


def _feature_view(f: PerformanceFeatureSet) -> PerformanceFeatureViewRow:
    return PerformanceFeatureViewRow(
        export_id=str(f.export_id),
        tenant_id=str(f.tenant_id),
        feature_version=f.feature_version,
        maturity_state=f.maturity_state,  # type: ignore[arg-type]
        engagement_confidence=f.engagement_confidence,
        normalized_view_rate=f.normalized_view_rate,
        normalized_completion_rate=f.normalized_completion_rate,
        normalized_watch_time=f.normalized_watch_time,
        replay_rate=f.replay_rate,
        share_rate=f.share_rate,
        engagement_score=f.engagement_score,
        experiment_group_id=str(f.experiment_group_id) if f.experiment_group_id else None,
    )


def _snapshot_view(s: RankingSnapshot) -> RankingSnapshotView:
    return RankingSnapshotView(
        id=str(s.id),
        tenant_id=str(s.tenant_id),
        candidate_id=str(s.candidate_id),
        job_id=str(s.job_id),
        source_export_id=str(s.source_export_id) if s.source_export_id else None,
        base_rank_score=s.base_rank_score,
        engagement_adjustment=s.engagement_adjustment,
        final_rank_score=s.final_rank_score,
        feature_version=s.feature_version,
        feedback_applied=s.feedback_applied,
        confidence_threshold=s.confidence_threshold,
        engagement_weight_cap=s.engagement_weight_cap,
        explanation=s.explanation,
        snapshot_metadata=s.snapshot_metadata or {},
        created_at=s.created_at.isoformat(),
    )


def _usage_view(u: UsageEvent) -> UsageEventView:
    return UsageEventView(
        id=str(u.id),
        tenant_id=str(u.tenant_id),
        user_id=str(u.user_id) if u.user_id else None,
        upload_id=str(u.upload_id) if u.upload_id else None,
        job_id=str(u.job_id) if u.job_id else None,
        event_type=u.event_type,
        quantity=u.quantity,
        unit=u.unit,
        estimated_cost_cents=u.estimated_cost_cents,
        event_metadata=u.event_metadata or {},
        created_at=u.created_at.isoformat(),
    )
