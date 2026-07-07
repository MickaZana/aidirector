"""Director Plans router — last segment of the MVP loop.

POST /api/jobs/{id}/director-plan persists a DirectorPlan validated against
the contract in apps/api/src/api/schemas/director_plan.py.
GET returns the latest plan for a job.
PATCH accepts user corrections (Adaptive Director Agent, Sprint 5.3).

In Phase 1, this route is called by the Director Agent worker. In Phase 0
it's also exposed publicly so the contract can be exercised end-to-end with
synthetic plans for testing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import DirectorPlan, Job, UsageEventType, PlanCorrection
from api.rate_limit import limiter
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
@limiter.limit("30/minute")
def create_director_plan(
    request: Request,
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


# ---------------------------------------------------------------------------
# Correction schemas
# ---------------------------------------------------------------------------


class PlanCorrectionIn(BaseModel):
    """Payload for PATCH — user's corrected DirectorPlan."""

    corrected_plan: DirectorPlanContract
    correction_type: str = Field(default="multiple", max_length=32)
    rationale: str | None = Field(default=None, max_length=1000)


class PlanCorrectionView(BaseModel):
    id: str
    job_id: str
    plan_id: str
    correction_type: str
    rationale: str | None
    original_summary: dict
    corrected_summary: dict
    applied_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.patch("", response_model=DirectorPlanView)
def correct_director_plan(
    job_id: uuid.UUID,
    req: PlanCorrectionIn,
    tenant: TenantRow,
    db: DbSession,
) -> DirectorPlanView:
    """Accept a user correction to a DirectorPlan.

    Persists the corrected plan as a NEW DirectorPlan row (so re-renders
    use the corrected version) AND records a PlanCorrection with snapshots
    of both versions for the learning loop.

    The corrected plan's job_id must match the URL job_id.
    """
    if req.corrected_plan.job_id != str(job_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"corrected_plan.job_id ({req.corrected_plan.job_id}) "
            f"does not match URL job_id ({job_id})",
        )

    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    # Load the latest plan (the one being corrected)
    original_row = db.execute(
        select(DirectorPlan)
        .where(DirectorPlan.job_id == job.id)
        .order_by(DirectorPlan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if original_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No director plan to correct")

    original_plan = DirectorPlanContract.model_validate(original_row.plan_json)
    now = datetime.now(timezone.utc)

    # 1. Persist the corrected plan as a new DirectorPlan row
    corrected_row = DirectorPlan(
        job_id=job.id,
        tenant_id=tenant.id,
        model=req.corrected_plan.model or original_row.model,
        prompt_version=f"{original_row.prompt_version}-corrected",
        plan_json=req.corrected_plan.model_dump(mode="json"),
    )
    db.add(corrected_row)
    db.flush()

    # 2. Record the correction snapshot
    correction = PlanCorrection(
        tenant_id=tenant.id,
        job_id=job.id,
        plan_id=corrected_row.id,
        original_plan_json=original_row.plan_json,
        corrected_plan_json=req.corrected_plan.model_dump(mode="json"),
        correction_type=req.correction_type,
        rationale=req.rationale,
        applied_at=now,
    )
    db.add(correction)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=tenant.id,
        job_id=job.id,
        event_type=UsageEventType.DIRECTOR_PLAN_CREATED,
        unit="correction",
        metadata={
            "correction_type": req.correction_type,
            "plan_id": str(corrected_row.id),
            "original_plan_id": str(original_row.id),
            "has_rationale": req.rationale is not None,
        },
    )
    db.commit()

    return _serialize(corrected_row, req.corrected_plan)


@router.get("/corrections", response_model=list[PlanCorrectionView])
def list_corrections(
    job_id: uuid.UUID,
    tenant: TenantRow,
    db: DbSession,
) -> list[PlanCorrectionView]:
    """List all PlanCorrections for a job (most recent first)."""
    job = db.execute(
        select(Job).where(Job.id == job_id, Job.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    rows = (
        db.execute(
            select(PlanCorrection)
            .where(PlanCorrection.job_id == job.id)
            .order_by(PlanCorrection.applied_at.desc())
        )
        .scalars()
        .all()
    )

    return [
        PlanCorrectionView(
            id=str(r.id),
            job_id=str(r.job_id),
            plan_id=str(r.plan_id),
            correction_type=r.correction_type,
            rationale=r.rationale,
            original_summary=_summarize_plan(r.original_plan_json),
            corrected_summary=_summarize_plan(r.corrected_plan_json),
            applied_at=r.applied_at.isoformat(),
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _summarize_plan(plan_json: dict) -> dict:
    """Extract a lightweight summary from plan JSON for the corrections list."""
    candidates = plan_json.get("selected_candidates", [])
    return {
        "candidate_count": len(candidates),
        "variant_count": sum(len(c.get("variants", [])) for c in candidates),
        "styles": list({c.get("render_style", "?") for c in candidates}),
        "pacing": list({c.get("pacing", "?") for c in candidates}),
        "cost_estimate_cents": plan_json.get("cost_estimate_cents"),
    }
