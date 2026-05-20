"""Worker heartbeat + stale-job detection.

A worker that holds a Job or RenderJob row must:
  1. `mark_worker_started(...)` — claim the row + set worker_id + heartbeat_at
  2. `mark_worker_heartbeat(...)` — bump heartbeat_at periodically while busy
  3. on success: drive `state_transitions.transition(... -> succeeded)`
  4. on failure: drive `state_transitions.transition(... -> failed)`

If step 2 stops (worker process killed, network split, OOM) the
`detect_stale_rows(...)` sweep picks them up: any row whose
`heartbeat_at < now - stale_after` and whose status is non-terminal is
marked stale. The sweep emits `WORKER_STALE_DETECTED` and is also the
hook a future supervisor will use to drive `failed → retrying → ...`
recovery flows.

This module never directly mutates `status`. State changes still go
through `state_transitions.transition(...)`. Heartbeat fields are
operational telemetry, not state.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable, TypeAlias

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import Job, JobStatus, RenderJob, RenderJobStatus, UsageEvent, UsageEventType

WorkerRow: TypeAlias = Job | RenderJob


# Default stale window — workers should heartbeat at least this often.
# Tuned for FFmpeg renders that can run minutes; bump for longer jobs.
DEFAULT_STALE_AFTER = timedelta(minutes=5)


def mark_worker_started(
    db: Session,
    row: WorkerRow,
    *,
    worker_id: str,
    started_at: datetime | None = None,
) -> None:
    """Claim a job for one worker. Idempotent for the same worker_id."""
    now = started_at or datetime.now(timezone.utc)
    if row.worker_id and row.worker_id != worker_id:
        # Someone else is holding this row. Refuse silently — the caller's
        # state guard will catch the underlying race when it tries to
        # transition the row.
        return
    row.worker_id = worker_id
    if row.started_at is None:
        row.started_at = now
    row.heartbeat_at = now
    db.add(
        UsageEvent(
            tenant_id=row.tenant_id,
            upload_id=getattr(row, "upload_id", None),
            job_id=row.id if isinstance(row, Job) else row.job_id,
            event_type=UsageEventType.WORKER_STARTED.value,
            quantity=1.0,
            unit="event",
            event_metadata={"worker_id": worker_id, "kind": type(row).__name__},
        )
    )


def mark_worker_heartbeat(
    db: Session,
    row: WorkerRow,
    *,
    worker_id: str,
    now: datetime | None = None,
    emit_event: bool = False,
) -> None:
    """Bump heartbeat_at. `emit_event=True` writes an audit row too —
    most callers should heartbeat silently and only audit on milestones."""
    if row.worker_id and row.worker_id != worker_id:
        return
    row.heartbeat_at = now or datetime.now(timezone.utc)
    if emit_event:
        db.add(
            UsageEvent(
                tenant_id=row.tenant_id,
                upload_id=getattr(row, "upload_id", None),
                job_id=row.id if isinstance(row, Job) else row.job_id,
                event_type=UsageEventType.WORKER_HEARTBEAT.value,
                quantity=1.0,
                unit="event",
                event_metadata={"worker_id": worker_id, "kind": type(row).__name__},
            )
        )


def mark_retry_initiated(
    db: Session,
    row: WorkerRow,
    *,
    reason: str,
    by_worker: str | None = None,
) -> None:
    """Bump retry_count + emit audit event. Does NOT change status —
    callers drive `state_transitions.transition(... -> "retrying")` first."""
    row.retry_count = (row.retry_count or 0) + 1
    db.add(
        UsageEvent(
            tenant_id=row.tenant_id,
            upload_id=getattr(row, "upload_id", None),
            job_id=row.id if isinstance(row, Job) else row.job_id,
            event_type=UsageEventType.WORKER_RETRY_INITIATED.value,
            quantity=1.0,
            unit="event",
            event_metadata={
                "kind": type(row).__name__,
                "retry_count": row.retry_count,
                "reason": reason,
                "by_worker": by_worker,
            },
        )
    )


def detect_stale_rows(
    db: Session,
    row_type: type[WorkerRow],
    *,
    stale_after: timedelta = DEFAULT_STALE_AFTER,
    now: datetime | None = None,
) -> list[WorkerRow]:
    """Find non-terminal rows whose worker has stopped heartbeating.

    Returns the offending rows + emits a `WORKER_STALE_DETECTED` event
    for each. Callers decide whether to drive them into `failed` or
    `retrying`; this function never mutates status.
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now - stale_after

    active_states = _active_states(row_type)
    rows = list(
        db.execute(
            select(row_type)
            .where(
                row_type.heartbeat_at.is_not(None),
                row_type.heartbeat_at < cutoff,
                row_type.status.in_(active_states),
            )
        ).scalars()
    )

    for row in rows:
        db.add(
            UsageEvent(
                tenant_id=row.tenant_id,
                upload_id=getattr(row, "upload_id", None),
                job_id=row.id if isinstance(row, Job) else row.job_id,
                event_type=UsageEventType.WORKER_STALE_DETECTED.value,
                quantity=1.0,
                unit="event",
                event_metadata={
                    "kind": row_type.__name__,
                    "worker_id": row.worker_id,
                    "heartbeat_at": row.heartbeat_at.isoformat() if row.heartbeat_at else None,
                    "stale_after_seconds": int(stale_after.total_seconds()),
                },
            )
        )
    return rows


def _active_states(row_type: type[WorkerRow]) -> frozenset[str]:
    """Non-terminal states that a worker should be heartbeating through."""
    if row_type is Job:
        return frozenset(
            {
                JobStatus.QUEUED.value,
                JobStatus.RUNNING.value,
                JobStatus.RETRYING.value,
            }
        )
    if row_type is RenderJob:
        return frozenset(
            {
                RenderJobStatus.QUEUED.value,
                RenderJobStatus.RENDERING.value,
                RenderJobStatus.RETRYING.value,
            }
        )
    raise TypeError(f"No active-state set for {row_type!r}")
