"""Persist ExportArtifact rows + emit lifecycle usage events.

Used by:
- workers.export_worker (after r2 upload + builder)
- the phase-6 probe (drives the same path without Modal)

Lifecycle:
  1. `persist_export_artifact(...)` → INSERT exports row (status=uploaded
     if storage_uri verified, else pending), emit EXPORT_CREATED.
  2. `mark_export_failed(...)` → UPDATE status=failed, emit JOB_FAILED.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.models import (
    ExportArtifact,
    ExportArtifactStatus,
    Job,
    RenderOutput,
    UsageEventType,
)
from api.services.export_artifact_builder import ExportArtifactInputs
from api.services.state_transitions import transition
from api.services.usage_events import emit_usage_event


def persist_export_artifact(
    db: Session,
    *,
    job: Job,
    render_output: RenderOutput,
    inputs: ExportArtifactInputs,
    status: ExportArtifactStatus = ExportArtifactStatus.UPLOADED,
    published_at: datetime | None = None,
) -> ExportArtifact:
    """INSERT one exports row + emit EXPORT_CREATED."""
    row = ExportArtifact(
        id=inputs.export_id,
        tenant_id=inputs.tenant_id,
        render_output_id=inputs.render_output_id,
        platform=inputs.platform,
        export_status=status.value,
        export_version=inputs.export_version,
        export_hash=inputs.export_hash,
        content_hash=inputs.content_hash,
        content_bytes=inputs.content_bytes,
        filename=inputs.filename,
        storage_uri=inputs.storage_uri,
        artifact_metadata=inputs.artifact_metadata,
        published_at=published_at,
    )
    db.add(row)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.EXPORT_CREATED,
        unit="export",
        metadata={
            "export_id": str(inputs.export_id),
            "render_output_id": str(inputs.render_output_id),
            "platform": inputs.platform,
            "export_version": inputs.export_version,
            "export_hash": inputs.export_hash,
            "content_hash": inputs.content_hash,
            "content_bytes": inputs.content_bytes,
            "storage_uri": inputs.storage_uri,
            "filename": inputs.filename,
        },
    )
    return row


def mark_export_failed(
    db: Session,
    *,
    job: Job,
    export: ExportArtifact,
    error: str,
    error_metadata: dict | None = None,
    worker_id: str | None = None,
) -> None:
    transition(
        db,
        export,
        ExportArtifactStatus.FAILED.value,
        reason=error,
        worker_id=worker_id,
    )
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.JOB_FAILED,
        unit="export",
        metadata={
            "export_id": str(export.id),
            "platform": export.platform,
            "error": error,
            **(error_metadata or {}),
        },
    )


def mark_export_published(
    db: Session,
    *,
    export: ExportArtifact,
    when: datetime | None = None,
    worker_id: str | None = None,
) -> None:
    """Flag an export as posted to its target platform. No new usage event
    beyond the TRANSITION_ACCEPTED row that the guard emits."""
    transition(
        db,
        export,
        ExportArtifactStatus.PUBLISHED.value,
        worker_id=worker_id,
    )
    export.published_at = when or datetime.now(timezone.utc)
    db.flush()
