"""Helper for emitting UsageEvent rows.

Single entry point so workers and routers can write events consistently.
Stripe meter event emission is wired separately (apps/api/services/billing.py)
and reads from the same UsageEvent rows.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from api.models import UsageEvent, UsageEventType


def emit_usage_event(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    event_type: UsageEventType,
    user_id: uuid.UUID | None = None,
    upload_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    quantity: float = 1.0,
    unit: str = "count",
    estimated_cost_cents: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> UsageEvent:
    """Insert one usage_event row. Caller is responsible for db.commit()."""
    event = UsageEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        upload_id=upload_id,
        job_id=job_id,
        event_type=event_type.value,
        quantity=quantity,
        unit=unit,
        estimated_cost_cents=estimated_cost_cents,
        event_metadata=metadata or {},
    )
    db.add(event)
    return event
