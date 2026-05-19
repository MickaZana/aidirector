"""Persist a validated DirectorPlan to the director_plans table.

Used by:
- workers.director_worker (after build + optional enrichment)
- the phase-4 local probe (drives the same path without Modal)

Emits one DIRECTOR_PLAN_CREATED usage event in the same transaction so
plan-creation and metering are atomic.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from api.models import DirectorPlan as DirectorPlanRow
from api.models import Job, UsageEventType
from api.schemas.director_plan import DirectorPlan as DirectorPlanContract
from api.services.usage_events import emit_usage_event


def persist_director_plan(
    db: Session,
    *,
    job: Job,
    plan: DirectorPlanContract,
) -> DirectorPlanRow:
    """Write a director_plans row + emit DIRECTOR_PLAN_CREATED.

    The plan must already be a validated DirectorPlan (Pydantic). We force
    one more `model_validate` pass here as a defense-in-depth guarantee that
    nothing partly-formed slips into the database.
    """
    validated = DirectorPlanContract.model_validate(plan.model_dump(mode="python"))

    row = DirectorPlanRow(
        id=uuid.uuid4(),
        job_id=job.id,
        tenant_id=job.tenant_id,
        model=validated.model,
        prompt_version=validated.prompt_version,
        plan_json=validated.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.DIRECTOR_PLAN_CREATED,
        unit="plan",
        estimated_cost_cents=validated.cost_estimate_cents,
        metadata={
            "model": validated.model,
            "prompt_version": validated.prompt_version,
            "candidates": len(validated.selected_candidates),
            "variants": sum(len(c.variants) for c in validated.selected_candidates),
            "platform_targets": list(validated.platform_targets),
        },
    )
    return row
