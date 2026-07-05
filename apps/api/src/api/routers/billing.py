"""Billing router — Stripe portal, usage stats, subscription info."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import extract, func, select

from api.deps import DbSession, TenantRow
from api.models import Job, UsageEvent, UsageEventType
from api.services.billing import (
    create_billing_portal_session,
    get_or_create_customer,
    get_subscription_status,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

_RETURN_URL_DEFAULT = "http://localhost:3001/app/settings/billing"


class PortalResponse(BaseModel):
    url: str


class UsageResponse(BaseModel):
    plan: str
    matches_used: int
    matches_limit: int | None
    exports_used: int
    current_period_end: str | None


class SubscriptionResponse(BaseModel):
    plan: str
    status: str
    current_period_end: str | None


@router.get("/portal", response_model=PortalResponse)
def portal(tenant: TenantRow) -> PortalResponse:
    """Return a Stripe Customer Portal session URL for the tenant."""
    customer_id = get_or_create_customer(
        tenant_id=str(tenant.id),
        email=tenant.name,
        name=tenant.name,
    )
    url = create_billing_portal_session(
        customer_id=customer_id,
        return_url=_RETURN_URL_DEFAULT,
    )
    return PortalResponse(url=url)


@router.get("/usage", response_model=UsageResponse)
def usage(tenant: TenantRow, db: DbSession) -> UsageResponse:
    """Return real usage counts for the current calendar month."""
    now = datetime.now(tz=timezone.utc)
    plan = getattr(tenant, "plan", "starter") or "starter"

    from api.services.billing import PLAN_MATCH_LIMITS
    limit = PLAN_MATCH_LIMITS.get(plan)

    matches_used = db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant.id,
            extract("year", Job.created_at) == now.year,
            extract("month", Job.created_at) == now.month,
        )
    ).scalar_one()

    exports_used = db.execute(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.event_type == UsageEventType.EXPORT_CREATED.value,
            extract("year", UsageEvent.created_at) == now.year,
            extract("month", UsageEvent.created_at) == now.month,
        )
    ).scalar_one()

    return UsageResponse(
        plan=plan,
        matches_used=matches_used,
        matches_limit=limit,
        exports_used=exports_used,
        current_period_end=None,
    )


@router.get("/subscription", response_model=SubscriptionResponse)
def subscription(tenant: TenantRow) -> SubscriptionResponse:
    """Return current Stripe subscription plan and status."""
    customer_id = get_or_create_customer(
        tenant_id=str(tenant.id),
        email=tenant.name,
        name=tenant.name,
    )
    info = get_subscription_status(customer_id)
    return SubscriptionResponse(
        plan=info["plan"],
        status=info["status"],
        current_period_end=info.get("current_period_end"),
    )
