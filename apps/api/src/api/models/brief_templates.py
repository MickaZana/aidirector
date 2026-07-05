"""BriefTemplate — reusable DirectorPlan brief presets.

Operators save sport context, style, pacing, and hook preferences as named
templates. A template can be applied at job-creation time to seed the Director
Agent brief without re-typing it each run.
"""
from __future__ import annotations

import uuid

from sqlalchemy import ARRAY, JSON, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


class BriefTemplate(Base, TimestampMixin):
    __tablename__ = "brief_templates"
    __table_args__ = (
        Index("ix_brief_templates_tenant_id", "tenant_id"),
        Index("ix_brief_templates_sport", "sport"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Editorial signals — all optional so partial templates are valid.
    sport: Mapped[str | None] = mapped_column(String(64), nullable=True)
    render_style: Mapped[str | None] = mapped_column(String(32), nullable=True)
    caption_style: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pacing: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Freeform hook phrases and searchable tags stored as JSON arrays.
    hook_phrases: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Marketplace fields — public templates are listed in the global marketplace.
    is_public: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    use_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
