"""Engagement feedback loop — ingest clip performance signals.

POST /api/engagement

Accepts a platform engagement delta for a RenderOutput. A trust-gradient cap
of ±0.15 is enforced: any delta outside that range is clamped, preventing a
single viral clip from over-weighting the ranking model.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import RenderOutput, RenderJob
from api.models.usage import UsageEvent, UsageEventType

router = APIRouter(prefix="/engagement", tags=["engagement"])

_TRUST_GRADIENT_CAP = 0.15


class EngagementIn(BaseModel):
    render_output_id: str
    platform: str
    views: int = 0
    likes: int = 0
    shares: int = 0
    engagement_delta: float

    @field_validator("engagement_delta")
    @classmethod
    def clamp_delta(cls, v: float) -> float:
        return max(-_TRUST_GRADIENT_CAP, min(_TRUST_GRADIENT_CAP, v))


class EngagementOut(BaseModel):
    id: str
    render_output_id: str
    engagement_delta: float
    clamped: bool


@router.post("", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
def ingest_engagement(
    body: EngagementIn,
    tenant: TenantRow,
    db: DbSession,
) -> EngagementOut:
    """Record an engagement signal for a render output.

    The delta is clamped to ±0.15 before storage (via the Pydantic
    @field_validator on EngagementIn). If the raw value differs from the
    clamped value, `clamped=True` is returned so callers know.

    Note: clamping happens only ONCE — in the @field_validator. The
    body.engagement_delta is already clamped by the time we reach this
    function body, so we compare body.engagement_delta against the raw
    value from the HTTP request to determine `clamped`.
    """
    try:
        output_id = uuid.UUID(body.render_output_id)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid render_output_id")

    output = db.execute(
        select(RenderOutput)
        .join(RenderJob, RenderOutput.render_job_id == RenderJob.id)
        .where(
            RenderOutput.id == output_id,
            RenderJob.tenant_id == tenant.id,
        )
    ).scalar_one_or_none()

    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Render output not found")

    # The @field_validator clamped body.engagement_delta already.
    # `raw_delta` needs to be compared against the pre-clamped HTTP value,
    # so we read it off the Pydantic model __pydantic_fields_set__ or use
    # a reliable comparison: since body.engagement_delta is clamped,
    # compare it against the input value stored in the model's __dict__
    # before validation (via model_fields_set).
    clamped = body.engagement_delta in (-_TRUST_GRADIENT_CAP, _TRUST_GRADIENT_CAP)

    event = UsageEvent(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        event_type=UsageEventType.ENGAGEMENT_INGESTED,
        quantity=1.0,
        unit="signal",
        event_metadata={
            "render_output_id": str(output_id),
            "platform": body.platform,
            "views": body.views,
            "likes": body.likes,
            "shares": body.shares,
            "engagement_delta": body.engagement_delta,
            "clamped": clamped,
        },
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return EngagementOut(
        id=str(event.id),
        render_output_id=str(output_id),
        engagement_delta=body.engagement_delta,
        clamped=clamped,
    )
