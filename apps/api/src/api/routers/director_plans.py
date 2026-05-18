"""Director Plans router — last segment of the MVP loop.

POST /api/jobs/{id}/director-plan persists a DirectorPlan validated against
the contract in apps/api/src/api/schemas/director_plan.py.
GET returns the latest plan for a job.

In Phase 1, this route is called by the Director Agent worker. In Phase 0
it's also exposed publicly so the contract can be exercised end-to-end with
synthetic plans for testing.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import DirectorPlan, Job, UsageEventType
from api.schemas.director_plan import DirectorPlan as DirectorPlanContract
from api.services.usage_events import emit_usage_event

router = APIRouter(prefix="/jobs/{job_id}/director-plan", tags=["director-plans"])


class DirectorPlanCreate(BaseModel):
    plan: DirectorPlanContract


class DirectorPlanView(BaseModel):
    id: str
    job_id: str
    tenant_id: str
    model: str
    prompt_version: str
    plan: DirectorPlanContract
    created_at: str


@router.post("", response_model=DirectorPlanView, status_code=status.HTTP_201_CREATED)
def create_director_plan(
    job_id: uuid.UUID,
    req: DirectorPlanCreate,
    tenant: TenantRow,
    db: DbSession,
) -> DirectorPlanView:
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    # Pydantic already validated. Enforce that the plan's job_id matches the URL.
    if req.plan.job_id != str(job.id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"plan.job_id ({req.plan.job_id}) does not match URL job_id ({job.id})",
        )

    row = DirectorPlan(
        job_id=job.id,
        tenant_id=tenant.id,
        model=req.plan.model,
        prompt_version=req.plan.prompt_version,
        plan_json=req.plan.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=tenant.id,
        job_id=job.id,
        event_type=UsageEventType.DIRECTOR_PLAN_CREATED,
        unit="plan",
        estimated_cost_cents=req.plan.cost_estimate_cents,
        metadata={
            "model": req.plan.model,
            "candidates": len(req.plan.selected_candidates),
            "variants": sum(len(c.variants) for c in req.plan.selected_candidates),
        },
    )
    db.commit()

    return _serialize(row, req.plan)


@router.get("", response_model=DirectorPlanView)
def get_latest_director_plan(
    job_id: uuid.UUID, tenant: TenantRow, db: DbSession
) -> DirectorPlanView:
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    row = db.execute(
        select(DirectorPlan)
        .where(DirectorPlan.job_id == job.id)
        .order_by(DirectorPlan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No director plan for this job")

    plan = DirectorPlanContract.model_validate(row.plan_json)
    return _serialize(row, plan)


def _serialize(row: DirectorPlan, plan: DirectorPlanContract) -> DirectorPlanView:
    return DirectorPlanView(
        id=str(row.id),
        job_id=str(row.job_id),
        tenant_id=str(row.tenant_id),
        model=row.model,
        prompt_version=row.prompt_version,
        plan=plan,
        created_at=row.created_at.isoformat(),
    )
