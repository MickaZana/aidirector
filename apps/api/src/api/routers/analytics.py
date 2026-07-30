from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from api.deps import AdminClaims, Claims, DbSession, TenantRow
from api.models.analytics import AnalyticsEvent

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsEventIn(BaseModel):
    event_id: str = Field(min_length=8, max_length=128)
    event_name: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    session_id: str | None = Field(default=None, max_length=128)
    project_id: str | None = Field(default=None, max_length=128)
    properties: dict[str, Any] = Field(default_factory=dict)


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
def ingest_event(payload: AnalyticsEventIn, db: DbSession, tenant: TenantRow, claims: Claims):
    existing = db.scalar(
        select(AnalyticsEvent).where(
            AnalyticsEvent.tenant_id == tenant.id,
            AnalyticsEvent.event_id == payload.event_id,
        )
    )
    if existing:
        return {"accepted": True, "duplicate": True, "event_id": payload.event_id}
    event = AnalyticsEvent(
        tenant_id=tenant.id,
        user_id=claims.user_id,
        event_id=payload.event_id,
        event_name=payload.event_name,
        occurred_at=payload.occurred_at,
        session_id=payload.session_id,
        project_id=payload.project_id,
        properties=payload.properties,
    )
    db.add(event)
    db.commit()
    return {"accepted": True, "duplicate": False, "event_id": payload.event_id}


@router.get("/admin/summary")
def admin_summary(db: DbSession, _admin: AdminClaims):
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    rows = db.execute(select(AnalyticsEvent.event_name, AnalyticsEvent.user_id, AnalyticsEvent.occurred_at)).all()
    events = [{"name": name, "user_id": user_id, "occurred_at": occurred_at} for name, user_id, occurred_at in rows]
    counts: dict[str, int] = {}
    for event in events:
        counts[event["name"]] = counts.get(event["name"], 0) + 1
    active_users = {event["user_id"] for event in events if event["occurred_at"] >= day_ago}
    return {
        "source": "first_party_backend",
        "generated_at": now.isoformat(),
        "total_events": len(events),
        "active_users_24h": len(active_users),
        "unique_users": len({event["user_id"] for event in events}),
        "counts": counts,
        "recent_events": [
            {"name": event["name"], "occurred_at": event["occurred_at"].isoformat()}
            for event in sorted(events, key=lambda item: item["occurred_at"], reverse=True)[:100]
        ],
    }
