"""Jobs router — second half of the MVP loop.

POST /api/jobs creates an analysis Job for an Upload and (in phase 1) enqueues
the Modal scene-analysis worker. GET returns the current state.

`/api/jobs/{id}/view` returns the JobView composite (everything a job-page
needs in one round-trip — see schemas/job_view.py). `/api/jobs/{id}/events`
is the cheap polling-friendly status refresh.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import Job, JobStatus, Upload, UsageEventType
from api.schemas.job_view import JobEventsView, JobView
from api.services.intel.omega_client import submodule_sha
from api.services.job_view_service import build_job_events, build_job_view
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

    # Phase 1: enqueue Modal worker here
    # queue.enqueue("scene_analysis", {"job_id": str(job.id), ...})

    return _serialize(job)


@router.get("", response_model=list[JobRowOut])
def list_jobs(tenant: TenantRow, db: DbSession) -> list[JobRowOut]:
    rows = (
        db.execute(
            select(Job).where(Job.tenant_id == tenant.id).order_by(Job.created_at.desc())
        )
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
