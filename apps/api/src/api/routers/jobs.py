"""Jobs router — second half of the MVP loop.

POST /api/jobs creates an analysis Job for an Upload and (in phase 1) enqueues
the Modal scene-analysis worker. GET returns the current state.

`/api/jobs/{id}/view` returns the JobView composite (everything a job-page
needs in one round-trip — see schemas/job_view.py). `/api/jobs/{id}/events`
is the cheap polling-friendly status refresh.

Sprint 6.2 additions:
  - POST /api/jobs/{id}/replay — deterministic replay (creates a new job
    with the same upload + inputs)
  - GET /api/jobs/{id}/audit — structured audit trail export (JSON)
  - GET /api/jobs/{id}/compliance-report — full compliance report
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import (
    ClipCandidate,
    DirectorPlan,
    ExportArtifact,
    Job,
    JobStatus,
    PlanCorrection,
    RenderJob,
    RenderOutput,
    Scene,
    Upload,
    UsageEvent,
    UsageEventType,
)
from api.services.billing import check_match_quota
from api.schemas.job_view import JobEventsView, JobView
from api.services.intel.omega_client import submodule_sha
from api.services.job_view_service import build_job_events, build_job_view
from api.services.queue import queue_for
from api.services.usage_events import emit_usage_event

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    upload_id: uuid.UUID
    intent: str = "analyze"
    cost_budget_cents: int = 30


class JobRowOut(BaseModel):
    id: str
    tenant_id: str
    upload_id: str
    intent: str
    status: str
    intel_submodule_sha: str | None
    error: str | None
    cost_budget_cents: int
    cost_actual_cents: int
    created_at: str


@router.post("", response_model=JobRowOut, status_code=status.HTTP_201_CREATED)
def create_job(req: JobCreate, tenant: TenantRow, db: DbSession) -> JobRowOut:
    plan = getattr(tenant, "plan", "starter") or "starter"
    check_match_quota(db, tenant_id=str(tenant.id), plan=plan)

    upload = db.execute(
        select(Upload).where(Upload.id == req.upload_id, Upload.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")

    job = Job(
        tenant_id=tenant.id,
        upload_id=upload.id,
        intent=req.intent,
        status=JobStatus.QUEUED.value,
        intel_submodule_sha=submodule_sha(),
        cost_budget_cents=req.cost_budget_cents,
    )
    db.add(job)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=tenant.id,
        upload_id=upload.id,
        job_id=job.id,
        event_type=UsageEventType.ANALYSIS_STARTED,
        unit="job",
        metadata={"intent": req.intent},
    )
    db.commit()

    # Dispatch: "analyze" → scene-analysis queue; "render" → render-cpu queue.
    # The render worker reads the DirectorPlan from DB by job_id, so only the
    # job_id (plus the source URI hint) needs to be in the payload.
    if req.intent == "render":
        queue_for("render-cpu").enqueue(
            "workers.render_worker.execute_render_job",
            {"job_id": str(job.id), "source_uri": str(upload.r2_key)},
            job_timeout=600,
            result_ttl=86400,
        )
    else:
        # Scene-analysis worker (to be implemented in Sprint 2 modal_app.py)
        # enqueues render-cpu itself after the DirectorPlan is persisted.
        queue_for("cv").enqueue(
            "workers.scene_analysis_worker.run_analysis",
            {"job_id": str(job.id)},
            job_timeout=900,
            result_ttl=86400,
        )

    return _serialize(job)


@router.get("", response_model=list[JobRowOut])
def list_jobs(tenant: TenantRow, db: DbSession) -> list[JobRowOut]:
    rows = (
        db.execute(select(Job).where(Job.tenant_id == tenant.id).order_by(Job.created_at.desc()))
        .scalars()
        .all()
    )
    return [_serialize(j) for j in rows]


@router.get("/{job_id}", response_model=JobRowOut)
def get_job(job_id: uuid.UUID, tenant: TenantRow, db: DbSession) -> JobRowOut:
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return _serialize(job)


@router.get("/{job_id}/view", response_model=JobView)
def get_job_view(job_id: uuid.UUID, tenant: TenantRow, db: DbSession) -> JobView:
    """Composite view — everything a job-page needs in one round-trip."""
    view = build_job_view(db, tenant=tenant, job_id=job_id)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return view


@router.get("/{job_id}/events", response_model=JobEventsView)
def get_job_events(job_id: uuid.UUID, tenant: TenantRow, db: DbSession) -> JobEventsView:
    """Cheap polling target — bump `revision` triggers a JobView refetch on the client."""
    events = build_job_events(db, tenant=tenant, job_id=job_id)
    if events is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return events


# ---------------------------------------------------------------------------
# Sprint 6.2 — Compliance suite
# ---------------------------------------------------------------------------


class JobReplayOut(BaseModel):
    """Response for POST /api/jobs/{id}/replay."""

    original_job_id: str
    new_job_id: str
    status: str
    message: str


@router.post("/{job_id}/replay", response_model=JobReplayOut, status_code=status.HTTP_201_CREATED)
def replay_job(
    job_id: uuid.UUID,
    tenant: TenantRow,
    db: DbSession,
) -> JobReplayOut:
    """Deterministic replay: create a NEW job with the SAME upload + inputs.

    The original job's analysis, plan, renders, and exports are preserved.
    The new job starts from QUEUED and runs through the full pipeline
    independently.

    Use cases:
      - A/B testing brief templates on the same source video
      - Verifying deterministic behaviour after a code change
      - Re-running a failed job after fixing root cause
    """
    original = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Original job not found")

    upload = db.execute(
        select(Upload).where(Upload.id == original.upload_id, Upload.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Original upload not found")

    # Create a new job with the same upload + same parameters
    replay = Job(
        tenant_id=tenant.id,
        upload_id=upload.id,
        intent=original.intent,
        status=JobStatus.QUEUED.value,
        intel_submodule_sha=submodule_sha(),
        cost_budget_cents=original.cost_budget_cents,
    )
    db.add(replay)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=tenant.id,
        upload_id=upload.id,
        job_id=replay.id,
        event_type=UsageEventType.ANALYSIS_STARTED,
        unit="replay",
        metadata={
            "original_job_id": str(original.id),
            "intent": original.intent,
            "reason": "user_requested_replay",
        },
    )
    db.commit()

    # Enqueue the new job for processing (same queue logic as create_job)
    if original.intent == "render":
        queue_for("render-cpu").enqueue(
            "workers.render_worker.execute_render_job",
            {"job_id": str(replay.id), "source_uri": str(upload.r2_key)},
            job_timeout=600,
            result_ttl=86400,
        )
    else:
        queue_for("cv").enqueue(
            "workers.scene_analysis_worker.run_analysis",
            {"job_id": str(replay.id)},
            job_timeout=900,
            result_ttl=86400,
        )

    return JobReplayOut(
        original_job_id=str(original.id),
        new_job_id=str(replay.id),
        status="queued",
        message="New job created with identical inputs for deterministic replay",
    )


# ---------------------------------------------------------------------------
# Audit trail export
# ---------------------------------------------------------------------------


@router.get("/{job_id}/audit")
def get_job_audit_trail(
    job_id: uuid.UUID,
    tenant: TenantRow,
    db: DbSession,
    format: str = "json",
) -> Response:
    """Structured audit trail for a job.

    Returns ALL UsageEvents, state transitions, and corrections for a job
    in chronological order. Available as JSON (default) or CSV (?format=csv).

    This is the compliance-ready audit trail for broadcasters / rights-holders.
    """
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    # Fetch all usage events for this job
    events = (
        db.execute(
            select(UsageEvent)
            .where(UsageEvent.job_id == job.id)
            .order_by(UsageEvent.created_at.asc())
        )
        .scalars()
        .all()
    )

    # Fetch any corrections
    corrections = (
        db.execute(
            select(PlanCorrection)
            .where(PlanCorrection.job_id == job.id)
            .order_by(PlanCorrection.applied_at.asc())
        )
        .scalars()
        .all()
    )

    # Build structured audit entries
    entries: list[dict[str, Any]] = []

    # Job lifecycle
    entries.append(
        {
            "timestamp": job.created_at.isoformat(),
            "type": "job_created",
            "detail": {
                "job_id": str(job.id),
                "upload_id": str(job.upload_id),
                "intent": job.intent,
                "status": job.status,
            },
        }
    )
    if job.started_at:
        entries.append(
            {
                "timestamp": job.started_at.isoformat(),
                "type": "job_started",
                "detail": {"worker_id": job.worker_id},
            }
        )
    if job.finished_at:
        entries.append(
            {
                "timestamp": job.finished_at.isoformat(),
                "type": "job_finished",
                "detail": {"status": job.status, "error": job.error},
            }
        )

    # Usage events
    for ev in events:
        entries.append(
            {
                "timestamp": ev.created_at.isoformat(),
                "type": f"usage_event:{ev.event_type}",
                "detail": {
                    "event_type": ev.event_type,
                    "quantity": ev.quantity,
                    "unit": ev.unit,
                    "metadata": ev.event_metadata,
                },
            }
        )

    # Corrections
    for c in corrections:
        entries.append(
            {
                "timestamp": c.applied_at.isoformat(),
                "type": f"correction:{c.correction_type}",
                "detail": {
                    "correction_type": c.correction_type,
                    "rationale": c.rationale,
                    "original_candidates": len(c.original_plan_json.get("selected_candidates", [])),
                    "corrected_candidates": len(
                        c.corrected_plan_json.get("selected_candidates", [])
                    ),
                },
            }
        )

    if format == "csv":
        return _audit_as_csv(entries, str(job.id))

    return _audit_as_json(entries, str(job.id))


def _audit_as_csv(entries: list[dict], job_id: str) -> Response:
    """Render audit trail as CSV."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "type", "detail"])
    for e in entries:
        writer.writerow([e["timestamp"], e["type"], str(e.get("detail", {}))])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="audit_{job_id}.csv"',
        },
    )


def _audit_as_json(entries: list[dict], job_id: str) -> Response:
    """Render audit trail as pretty-printed JSON."""
    import json

    return Response(
        content=json.dumps({"job_id": job_id, "audit_trail": entries}, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": f'inline; filename="audit_{job_id}.json"',
        },
    )


# ---------------------------------------------------------------------------
# Compliance report
# ---------------------------------------------------------------------------


@router.get("/{job_id}/compliance-report")
def get_compliance_report(
    job_id: uuid.UUID,
    tenant: TenantRow,
    db: DbSession,
) -> Response:
    """Full compliance report for broadcasting/rights-holder requirements.

    Combines: job metadata, upload info, scenes, clip candidates, director
    plan, render jobs + outputs, exports, and the full audit trail into a
    single structured document.

    Returned as downloadable JSON.
    """
    import json

    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    # Upload
    upload = db.execute(select(Upload).where(Upload.id == job.upload_id)).scalar_one_or_none()

    # Scenes
    scenes = (
        db.execute(select(Scene).where(Scene.job_id == job.id).order_by(Scene.t_start.asc()))
        .scalars()
        .all()
    )

    # Clip candidates
    candidates = (
        db.execute(
            select(ClipCandidate)
            .where(ClipCandidate.job_id == job.id)
            .order_by(ClipCandidate.confidence_score.desc().nullslast())
        )
        .scalars()
        .all()
    )

    # Director plans
    plans = (
        db.execute(
            select(DirectorPlan)
            .where(DirectorPlan.job_id == job.id)
            .order_by(DirectorPlan.created_at.desc())
        )
        .scalars()
        .all()
    )

    # Render jobs + outputs
    render_jobs = (
        db.execute(
            select(RenderJob).where(RenderJob.job_id == job.id).order_by(RenderJob.created_at.asc())
        )
        .scalars()
        .all()
    )
    render_outputs = (
        (
            db.execute(
                select(RenderOutput)
                .where(RenderOutput.tenant_id == tenant.id)
                .order_by(RenderOutput.created_at.asc())
            )
            .scalars()
            .all()
        )
        if render_jobs
        else []
    )

    # Exports
    exports = (
        (
            db.execute(
                select(ExportArtifact)
                .where(ExportArtifact.tenant_id == tenant.id)
                .order_by(ExportArtifact.created_at.asc())
            )
            .scalars()
            .all()
        )
        if render_outputs
        else []
    )

    # Audit events
    audit_events = (
        db.execute(
            select(UsageEvent)
            .where(UsageEvent.job_id == job.id)
            .order_by(UsageEvent.created_at.asc())
        )
        .scalars()
        .all()
    )

    report = {
        "report_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1",
            "tenant_id": str(tenant.id),
        },
        "job": {
            "id": str(job.id),
            "upload_id": str(job.upload_id),
            "intent": job.intent,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "error": job.error,
            "cost_budget_cents": job.cost_budget_cents,
            "cost_actual_cents": job.cost_actual_cents,
            "pipeline_timing": job.pipeline_timing,
            "intel_submodule_sha": job.intel_submodule_sha,
        },
        "upload": {
            "id": str(upload.id) if upload else None,
            "filename": upload.filename if upload else None,
            "bytes": upload.bytes if upload else None,
            "duration_s": upload.duration_s if upload else None,
            "sport": upload.sport if upload else None,
            "r2_key": upload.r2_key if upload else None,
        },
        "scenes": [
            {
                "id": str(s.id),
                "t_start": s.t_start,
                "t_end": s.t_end,
                "kind": s.kind,
                "arc_position": s.arc_position,
                "intensity": s.intensity,
                "importance": s.importance,
                "signals": s.signals,
            }
            for s in scenes
        ],
        "clip_candidates": [
            {
                "id": str(c.id),
                "scene_id": str(c.scene_id) if c.scene_id else None,
                "t_start": c.t_start,
                "t_end": c.t_end,
                "confidence_score": c.confidence_score,
                "quality_score": c.quality_score,
                "platform_score": c.platform_score,
                "virality_score": c.virality_score,
                "novelty_score": c.novelty_score,
                "rationale": c.rationale,
                "scores": c.scores,
            }
            for c in candidates
        ],
        "director_plans": [
            {
                "id": str(p.id),
                "model": p.model,
                "prompt_version": p.prompt_version,
                "plan_summary": {
                    "candidates": len(p.plan_json.get("selected_candidates", [])),
                    "variants": sum(
                        len(c.get("variants", []))
                        for c in p.plan_json.get("selected_candidates", [])
                    ),
                    "cost_estimate_cents": p.plan_json.get("cost_estimate_cents"),
                },
                "created_at": p.created_at.isoformat(),
            }
            for p in plans
        ],
        "renders": [
            {
                "id": str(rj.id),
                "candidate_id": str(rj.candidate_id),
                "pipeline": rj.pipeline,
                "platform": rj.platform,
                "status": rj.status,
                "error": rj.error,
                "started_at": rj.started_at.isoformat() if rj.started_at else None,
                "finished_at": rj.finished_at.isoformat() if rj.finished_at else None,
                "cost_cents": rj.cost_cents,
                "gpu_seconds": rj.gpu_seconds,
            }
            for rj in render_jobs
        ],
        "exports": [
            {
                "id": str(e.id),
                "render_output_id": str(e.render_output_id),
                "platform": e.platform,
                "status": e.export_status,
                "content_hash": e.content_hash,
                "export_hash": e.export_hash,
                "storage_uri": e.storage_uri,
                "created_at": e.created_at.isoformat(),
            }
            for e in exports
        ],
        "audit_trail": [
            {
                "timestamp": ev.created_at.isoformat(),
                "event_type": ev.event_type,
                "quantity": ev.quantity,
                "unit": ev.unit,
                "metadata": ev.event_metadata,
            }
            for ev in audit_events
        ],
    }

    return Response(
        content=json.dumps(report, indent=2, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="compliance_{job_id}.json"',
        },
    )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize(job: Job) -> JobRowOut:
    return JobRowOut(
        id=str(job.id),
        tenant_id=str(job.tenant_id),
        upload_id=str(job.upload_id),
        intent=job.intent,
        status=job.status,
        intel_submodule_sha=job.intel_submodule_sha,
        error=job.error,
        cost_budget_cents=job.cost_budget_cents,
        cost_actual_cents=job.cost_actual_cents,
        created_at=job.created_at.isoformat(),
    )
