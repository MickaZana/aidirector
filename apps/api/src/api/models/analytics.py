"""First-party, tenant-scoped product analytics events."""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Index, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


class AnalyticsEvent(Base, TimestampMixin):
    __tablename__ = "analytics_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", name="uq_analytics_events_tenant_event"),
        Index("ix_analytics_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_analytics_events_name_created", "event_name", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
