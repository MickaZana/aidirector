from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter

from api.config import get_settings

router = APIRouter()
log = logging.getLogger(__name__)

_QUEUES = ["q:render-cpu", "q:cv", "q:llm", "q:export"]


@router.get("/health")
def health() -> dict[str, Any]:
    """Aggregate health — checks all dependencies and returns a summary.

    Always returns HTTP 200 so load balancers don't drop traffic.
    Ops dashboards alert on `status: "degraded"`.
    """
    db_status = _check_db()
    queue_status = _check_queue()
    stripe_status = _check_stripe()
    r2_status = _check_r2()

    all_ok = all(
        s.get("status") == "ok" for s in [db_status, queue_status, stripe_status, r2_status]
    )
    return {
        "status": "ok" if all_ok else "degraded",
        "checks": {
            "db": db_status,
            "queue": queue_status,
            "stripe": stripe_status,
            "r2": r2_status,
        },
    }


@router.get("/health/db")
def health_db() -> dict:
    """Database connectivity check with SELECT 1 latency measurement."""
    return _check_db()


@router.get("/health/queue")
def health_queue() -> dict:
    """Redis connectivity check + per-queue depth."""
    return _check_queue()


@router.get("/health/stripe")
def health_stripe() -> dict:
    """Stripe API connectivity check."""
    return _check_stripe()


@router.get("/health/r2")
def health_r2() -> dict:
    """R2 / local-storage connectivity check."""
    return _check_r2()


# ── Individual check helpers ─────────────────────────────────────────────────


def _check_db() -> dict:
    try:
        from sqlalchemy import text
        from api.db import engine

        if engine is None:
            return {
                "status": "degraded",
                "error": "DATABASE_URL not configured",
                "latency_ms": None,
            }
        t0 = time.perf_counter()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        log.warning("health_db: database unreachable: %s", exc)
        return {"status": "degraded", "error": str(exc), "latency_ms": None}


def _check_queue() -> dict:
    try:
        from api.services.queue import queue_for

        depths: dict[str, int] = {}
        for name in _QUEUES:
            q = queue_for(name)
            depths[name] = len(q)
        return {"status": "ok", "queues": depths}
    except Exception as exc:
        log.warning("health_queue: redis unreachable: %s", exc)
        return {"status": "degraded", "error": str(exc), "queues": {}}


def _check_stripe() -> dict:
    """Check Stripe API by attempting to list customers (limit=1)."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        return {"status": "degraded", "error": "STRIPE_SECRET_KEY not configured"}
    try:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        stripe.Customer.list(limit=1)
        return {"status": "ok"}
    except Exception as exc:
        log.warning("health_stripe: stripe unreachable: %s", exc)
        return {"status": "degraded", "error": str(exc)}


def _check_r2() -> dict:
    """Check R2 / local-storage by calling head_object on a known key."""
    try:
        from api.services import r2 as r2_svc

        if not r2_svc.is_r2_configured():
            # In local mode, verify the local mirror directory exists
            mirror = r2_svc.local_mirror_path()
            if not mirror.exists():
                mirror.mkdir(parents=True, exist_ok=True)
            return {"status": "ok", "mode": "local", "mirror": str(mirror)}
        # In R2 mode, try a simple HEAD on the bucket root
        settings = get_settings()
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        client.head_bucket(Bucket=settings.r2_bucket)
        return {"status": "ok", "mode": "r2"}
    except Exception as exc:
        log.warning("health_r2: storage unreachable: %s", exc)
        return {"status": "degraded", "error": str(exc)}
