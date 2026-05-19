"""ExportArtifact — canonical distributable identity.

A RenderOutput is the *renderer's* result (file on storage + technical
metadata). An ExportArtifact is the *user-facing* publishable identity:
the thing that gets uploaded to YouTube/TikTok/Reels/X, the thing
analytics attaches to, the thing engagement labels feed back through.

The two are separate by design:
  - Re-renders may produce new RenderOutputs but the same ExportArtifact
    identity can survive (versioned).
  - Cross-platform variants share a content_hash even with different
    storage URIs.
  - Analytics never attaches to RenderOutput — that would pollute the
    feedback loop when retries happen.

Lineage: every ExportArtifact links back to exactly one RenderOutput
(the one that produced the bytes for THIS export_version).
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base, TimestampMixin, uuid_pk


class ExportArtifactStatus(str, enum.Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PUBLISHED = "published"
    FAILED = "failed"


class ExportArtifact(Base, TimestampMixin):
    __tablename__ = "exports"
    __table_args__ = (
        Index("ix_exports_tenant_id_platform", "tenant_id", "platform"),
        Index("ix_exports_tenant_id_created_at", "tenant_id", "created_at"),
        Index("ix_exports_render_output_id", "render_output_id"),
        Index("ix_exports_export_hash", "export_hash", unique=True),
        Index("ix_exports_content_hash", "content_hash"),
        Index("ix_exports_export_status", "export_status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    render_output_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("render_outputs.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    export_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ExportArtifactStatus.PENDING.value
    )
    export_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # export_hash = sha256(render_output_id|platform|export_version)
    # Stable, unique identity for THIS export. Re-running export keeps the
    # same hash; bumping version produces a new hash.
    export_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # content_hash = sha256(file bytes). Same file → same content_hash
    # across versions, retries, and even cross-platform variants if the
    # rendered bytes happen to match.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_bytes: Mapped[int | None] = mapped_column(nullable=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    artifact_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
