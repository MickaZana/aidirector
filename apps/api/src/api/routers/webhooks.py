"""Webhook receivers — Clerk and Stripe.

Both endpoints verify the request signature before touching the database.
A 400 is returned on any signature failure so the provider retries with
the correct secret rather than silently swallowing events.
"""

from __future__ import annotations

import logging

import stripe
from stripe import SignatureVerificationError as _StripeSignatureVerificationError
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from svix.webhooks import Webhook, WebhookVerificationError

from api.config import get_settings
from api.db import get_db
from api.models import User
from api.services.tenancy import get_or_create_tenant_by_ids

log = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Clerk ─────────────────────────────────────────────────────────────────────


@router.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(request: Request) -> dict[str, str]:
    """Verify Svix signature then process Clerk user/org lifecycle events."""
    settings = get_settings()
    secret = settings.clerk_webhook_secret
    if not secret:
        log.error("clerk_webhook: CLERK_WEBHOOK_SECRET not set — rejecting")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Webhook secret not configured")

    payload = await request.body()
    headers = dict(request.headers)

    try:
        wh = Webhook(secret)
        event = wh.verify(payload, headers)
    except WebhookVerificationError as exc:
        log.warning("clerk_webhook: signature verification failed — %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    event_type: str = event.get("type", "")
    data: dict = event.get("data", {})
    log.info("clerk_webhook: received %s", event_type)

    db_gen = get_db()
    db = next(db_gen)
    try:
        if event_type in ("user.created", "user.updated"):
            _upsert_user(db, data)
        elif event_type == "user.deleted":
            _soft_delete_user(db, data)
        elif event_type in ("organization.created", "organization.updated"):
            _upsert_org_tenant(db, data)
        elif event_type == "organizationMembership.created":
            _handle_org_membership(db, data)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("clerk_webhook: db error handling %s", event_type)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal error")
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    return {"received": "true"}


def _upsert_user(db, data: dict) -> None:
    clerk_user_id = data.get("id", "")
    email = (data.get("email_addresses") or [{}])[0].get("email_address", "")
    org_id = data.get("primary_organization_id") or clerk_user_id

    tenant = get_or_create_tenant_by_ids(db, org_id=org_id, org_name=email.split("@")[0])

    existing = db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    ).scalar_one_or_none()

    if existing:
        existing.email = email
    else:
        db.add(
            User(
                tenant_id=tenant.id,
                clerk_user_id=clerk_user_id,
                email=email,
            )
        )
    log.info("clerk_webhook: upserted user %s", clerk_user_id)


def _soft_delete_user(db, data: dict) -> None:
    clerk_user_id = data.get("id", "")
    user = db.execute(select(User).where(User.clerk_user_id == clerk_user_id)).scalar_one_or_none()
    if user:
        db.delete(user)
        log.info("clerk_webhook: deleted user %s", clerk_user_id)


def _upsert_org_tenant(db, data: dict) -> None:
    org_id = data.get("id", "")
    org_name = data.get("name", org_id)
    get_or_create_tenant_by_ids(db, org_id=org_id, org_name=org_name)
    log.info("clerk_webhook: upserted org tenant %s", org_id)


def _handle_org_membership(db, data: dict) -> None:
    org_id = data.get("organization", {}).get("id", "")
    org_name = data.get("organization", {}).get("name", org_id)
    if org_id:
        get_or_create_tenant_by_ids(db, org_id=org_id, org_name=org_name)


# ── Stripe ────────────────────────────────────────────────────────────────────


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Verify Stripe-Signature header then handle subscription/invoice events."""
    settings = get_settings()
    webhook_secret = settings.stripe_webhook_secret
    if not webhook_secret:
        log.error("stripe_webhook: STRIPE_WEBHOOK_SECRET not set — rejecting")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Webhook secret not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except _StripeSignatureVerificationError as exc:
        log.warning("stripe_webhook: signature verification failed — %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid Stripe signature")
    except Exception as exc:
        log.warning("stripe_webhook: payload parse error — %s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payload")

    event_type: str = event["type"]
    data = event["data"]["object"]
    log.info("stripe_webhook: received %s", event_type)

    if event_type == "invoice.payment_succeeded":
        _handle_payment_succeeded(data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data)

    return {"received": "true"}


def _handle_payment_succeeded(invoice: dict) -> None:
    customer_id = invoice.get("customer", "")
    amount = invoice.get("amount_paid", 0)
    log.info("stripe_webhook: payment succeeded customer=%s amount=%s", customer_id, amount)


def _handle_payment_failed(invoice: dict) -> None:
    customer_id = invoice.get("customer", "")
    log.warning("stripe_webhook: payment FAILED customer=%s", customer_id)


def _handle_subscription_deleted(sub: dict) -> None:
    """Downgrade tenant to Starter on subscription deletion."""
    customer_id = sub.get("customer", "")
    log.warning(
        "stripe_webhook: subscription deleted customer=%s — downgrading tenant", customer_id
    )
    _update_tenant_plan(customer_id, "starter")


def _handle_subscription_updated(sub: dict) -> None:
    """Sync tenant plan with the Stripe subscription's price ID."""
    customer_id = sub.get("customer", "")
    status = sub.get("status", "")
    if status != "active":
        return  # only sync active subscriptions

    items = sub.get("items", {}).get("data", [])
    if not items:
        return

    price_id = items[0].get("price", {}).get("id", "")
    plan = _price_to_plan(price_id)
    log.info("stripe_webhook: subscription updated customer=%s plan=%s", customer_id, plan)
    _update_tenant_plan(customer_id, plan)


def _price_to_plan(price_id: str) -> str:
    from api.config import get_settings

    s = get_settings()
    if s.stripe_price_pro and price_id == s.stripe_price_pro:
        return "pro"
    if s.stripe_price_studio and price_id == s.stripe_price_studio:
        return "studio"
    return "starter"


def _update_tenant_plan(customer_id: str, plan: str) -> None:
    """Persist a plan change to the Tenant row, identified by stripe_customer_id."""
    try:
        from sqlalchemy import select
        from api.db import get_db
        from api.models.tenancy import Tenant

        db_gen = get_db()
        db = next(db_gen)
        try:
            tenant = db.execute(
                select(Tenant).where(Tenant.stripe_customer_id == customer_id)
            ).scalar_one_or_none()
            if tenant is None:
                log.warning("stripe_webhook: no tenant found for customer %s", customer_id)
                return
            tenant.plan = plan
            db.commit()
            log.info("stripe_webhook: tenant %s plan updated to %s", tenant.id, plan)
        except Exception:
            db.rollback()
            raise
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
    except Exception as exc:
        log.error(
            "stripe_webhook: failed to update tenant plan for customer %s: %s", customer_id, exc
        )
