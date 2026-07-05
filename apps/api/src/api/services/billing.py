"""Stripe billing service — customer lifecycle, usage metering, quota checks.

Plan limits (matches landing page pricing):
  starter : 5 matches/month,  unlimited exports, 720p
  pro     : 50 matches/month, unlimited exports, 1080p
  studio  : unlimited matches, unlimited exports, 4K
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

import stripe

from api.config import get_settings

log = logging.getLogger(__name__)

Plan = Literal["starter", "pro", "studio"]

PLAN_MATCH_LIMITS: dict[str, int | None] = {
    "starter": 5,
    "pro": 50,
    "studio": None,  # unlimited
}


def _stripe_configured() -> bool:
    return bool(get_settings().stripe_secret_key)


def _ensure_stripe() -> None:
    s = get_settings()
    if s.stripe_secret_key:
        stripe.api_key = s.stripe_secret_key


# ── Customer lifecycle ────────────────────────────────────────────────────────


def get_or_create_customer(tenant_id: str, email: str, name: str = "") -> str:
    """Return existing Stripe customer_id or create one."""
    if not _stripe_configured():
        log.warning("billing: Stripe not configured — returning dev stub customer")
        return f"cus_dev_{tenant_id[:8]}"

    _ensure_stripe()
    existing = stripe.Customer.search(query=f'metadata["tenant_id"]:"{tenant_id}"', limit=1)
    if existing.data:
        return existing.data[0].id

    customer = stripe.Customer.create(
        email=email,
        name=name or email,
        metadata={"tenant_id": tenant_id},
    )
    log.info("billing: created Stripe customer %s for tenant %s", customer.id, tenant_id)
    return customer.id


def create_billing_portal_session(customer_id: str, return_url: str) -> str:
    """Return a Stripe Customer Portal session URL."""
    if not _stripe_configured():
        return return_url  # dev fallback: send back to app

    _ensure_stripe()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session.url


def get_subscription_status(customer_id: str) -> dict:
    """Return current subscription plan name and status."""
    if not _stripe_configured():
        return {"plan": "starter", "status": "active", "current_period_end": None}

    _ensure_stripe()
    subs = stripe.Subscription.list(customer=customer_id, limit=1, status="active")
    if not subs.data:
        return {"plan": "starter", "status": "none", "current_period_end": None}

    sub = subs.data[0]
    price_id = sub["items"]["data"][0]["price"]["id"]
    plan = _price_to_plan(price_id)
    period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc).isoformat()
    return {"plan": plan, "status": sub["status"], "current_period_end": period_end}


def _price_to_plan(price_id: str) -> Plan:
    s = get_settings()
    if s.stripe_price_pro and price_id == s.stripe_price_pro:
        return "pro"
    if s.stripe_price_studio and price_id == s.stripe_price_studio:
        return "studio"
    return "starter"


# ── Usage metering ────────────────────────────────────────────────────────────


def record_meter_event(
    customer_id: str,
    meter_name: Literal["match", "asr_minute", "gpu_second", "export"],
    quantity: int = 1,
) -> None:
    """Report usage to Stripe Meters for metered billing."""
    if not _stripe_configured():
        log.debug("billing: Stripe not configured — skipping meter event %s", meter_name)
        return

    _ensure_stripe()
    s = get_settings()
    meter_id_map = {
        "asr_minute": s.stripe_meter_asr_minutes,
        "gpu_second": s.stripe_meter_gpu_seconds,
        "export": s.stripe_meter_export_count,
    }
    meter_id = meter_id_map.get(meter_name, "")
    if not meter_id:
        log.debug("billing: no meter ID configured for %s", meter_name)
        return

    try:
        stripe.billing.MeterEvent.create(
            event_name=meter_name,
            payload={"stripe_customer_id": customer_id, "value": str(quantity)},
        )
    except Exception:
        log.exception("billing: failed to record meter event %s", meter_name)


def record_meter_for_tenant(
    db,
    tenant_id: str,
    meter_name: Literal["match", "asr_minute", "gpu_second", "export"],
    quantity: int = 1,
) -> None:
    """Look up the tenant's stripe_customer_id and record a meter event.

    This is the preferred entry point for pipeline stages — it resolves
    the customer_id from the Tenant row so callers don't need to fetch it
    themselves.
    """
    from sqlalchemy import select
    from api.models.tenancy import Tenant

    tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
    if tenant is None or not tenant.stripe_customer_id:
        log.debug(
            "billing: no stripe_customer_id for tenant %s — skipping meter %s",
            tenant_id,
            meter_name,
        )
        return
    record_meter_event(tenant.stripe_customer_id, meter_name, quantity)


# ── Quota enforcement ─────────────────────────────────────────────────────────


def check_match_quota(db, tenant_id: str, plan: str = "starter") -> None:
    """Raise HTTP 402 if tenant has exceeded their monthly match limit.

    Counts Job rows created this calendar month for the tenant.
    Respects the `enforce_quotas` feature flag — when disabled, all
    quotas are bypassed (useful for staging/demo environments).
    """
    from api.feature_flags import flag

    if not flag("enforce_quotas"):
        return

    from fastapi import HTTPException, status
    from sqlalchemy import func, select, extract
    from api.models import Job

    limit = PLAN_MATCH_LIMITS.get(plan)
    if limit is None:
        return  # unlimited

    now = datetime.now(tz=timezone.utc)
    count = db.execute(
        select(func.count(Job.id)).where(
            Job.tenant_id == tenant_id,
            extract("year", Job.created_at) == now.year,
            extract("month", Job.created_at) == now.month,
        )
    ).scalar_one()

    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Monthly match limit reached ({count}/{limit} on {plan} plan). "
                "Upgrade to Pro for 50 matches/month or Studio for unlimited."
            ),
        )
