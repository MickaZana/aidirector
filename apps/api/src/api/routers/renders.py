"""Renders router — read-only visibility into per-job render results.

GET /api/renders?job_id=<uuid>   list all RenderJob rows for a job
GET /api/renders/<render_job_id> single RenderJob + its RenderOutput (if any)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import RenderJob, RenderOutput

router = APIRouter(prefix="/renders", tags=["renders"])


class RenderOutputOut(BaseModel):
    id: str
    r2_key: str
    aspect_ratio: str
    duration_s: float | None
    bytes: int | None
    output_metadata: dict


class RenderJobOut(BaseModel):
    id: str
    job_id: str
    candidate_id: str
    pipeline: str
    platform: str
    status: str
    error: str | None
    cost_cents: int
    created_at: str
    finished_at: str | None
    output: RenderOutputOut | None


@router.get("", response_model=list[RenderJobOut])
def list_renders(job_id: uuid.UUID, tenant: TenantRow, db: DbSession) -> list[RenderJobOut]:
    """All render jobs for a given job, scoped to the calling tenant."""
    rows = (
        db.execute(
            select(RenderJob)
            .where(RenderJob.job_id == job_id, RenderJob.tenant_id == tenant.id)
            .order_by(RenderJob.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [_serialize(db, r) for r in rows]


@router.get("/{render_job_id}", response_model=RenderJobOut)
def get_render(render_job_id: uuid.UUID, tenant: TenantRow, db: DbSession) -> RenderJobOut:
    row = db.execute(
        select(RenderJob).where(
            RenderJob.id == render_job_id, RenderJob.tenant_id == tenant.id
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Render job not found")
    return _serialize(db, row)


# --- helpers ----------------------------------------------------------------

def _serialize(db: DbSession, rj: RenderJob) -> RenderJobOut:
    output_row = db.execute(
        select(RenderOutput).where(RenderOutput.render_job_id == rj.id)
    ).scalar_one_or_none()

    output = None
    if output_row is not None:
        output = RenderOutputOut(
            id=str(output_row.id),
            r2_key=output_row.r2_key,
            aspect_ratio=output_row.aspect_ratio,
            duration_s=output_row.duration_s,
            bytes=output_row.bytes,
            output_metadata=output_row.output_metadata or {},
        )

    return RenderJobOut(
        id=str(rj.id),
        job_id=str(rj.job_id),
        candidate_id=str(rj.candidate_id),
        pipeline=rj.pipeline,
        platform=rj.platform,
        status=rj.status,
        error=rj.error,
        cost_cents=rj.cost_cents,
        created_at=rj.created_at.isoformat(),
        finished_at=rj.finished_at.isoformat() if rj.finished_at else None,
        output=output,
    )
