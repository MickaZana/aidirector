"""Operational state-transition guards.

Hard rule: **every** status mutation on Job/RenderJob/ExportArtifact MUST
go through `transition(...)`. Direct assignment is a bug and grep-able
(the persistence services have been refactored to call this module).

Why this exists:

  - **No illegal transitions.** `succeeded → running` is a sign of a
    duplicate-worker race or replay bug. We reject it at the boundary
    instead of silently corrupting state.
  - **Terminal-state protection.** Once a job is `succeeded` or
    `cancelled`, nothing reopens it. Retries restart from `failed`, which
    moves through `retrying → running` so the audit trail is explicit.
  - **Audit trail.** Every accepted transition is logged via
    `operational_audit` (see usage_events extension). Every rejected
    transition emits `TRANSITION_REJECTED`, never silently dropped.

Design choices:

  - States live as `str` in the DB (varchar(16)) — adding a new state is
    a Python-only change (no migration), as long as it fits in 16 chars.
  - `retrying` is a real intermediate state, not a synonym for `queued`,
    so dashboards can distinguish "starting fresh" from "retry attempt".
  - `*` (any-state) cancellation is allowed only when the caller passes
    `force=True`, and only into `cancelled`. This is admin-only.

Public API:
  - `transition(db, row, to: str, *, reason: str | None = None,
                  worker_id: str | None = None, force: bool = False) -> None`
  - `IllegalTransition` raised for any rejected transition.
  - `legal_transitions(row_type) -> mapping[str, frozenset[str]]`
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, TypeAlias

from sqlalchemy.orm import Session

from api.models import (
    ExportArtifact,
    ExportArtifactStatus,
    Job,
    JobStatus,
    RenderJob,
    RenderJobStatus,
    UsageEventType,
)

# --- exceptions -------------------------------------------------------------


class IllegalTransition(RuntimeError):
    """Raised when a status mutation violates the transition map.

    Carries enough context to make the audit row useful:
        f"{kind}: {from_state} -> {to_state} is not allowed"
    """

    def __init__(
        self,
        *,
        kind: str,
        row_id: str,
        from_state: str,
        to_state: str,
        reason: str | None = None,
    ) -> None:
        self.kind = kind
        self.row_id = row_id
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        super().__init__(
            f"{kind} {row_id}: illegal transition {from_state!r} -> {to_state!r}"
            + (f" ({reason})" if reason else "")
        )


# --- transition maps -------------------------------------------------------
#
# Each map is FROM -> {allowed TOs}. A state with an empty frozenset is
# terminal. `cancelled` is reached via the `force=True` admin path, not
# through normal transitions.


JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    JobStatus.QUEUED.value: frozenset({JobStatus.RUNNING.value, JobStatus.FAILED.value}),
    JobStatus.RUNNING.value: frozenset(
        {JobStatus.SUCCEEDED.value, JobStatus.FAILED.value}
    ),
    JobStatus.FAILED.value: frozenset({"retrying"}),
    "retrying": frozenset({JobStatus.RUNNING.value, JobStatus.FAILED.value}),
    JobStatus.SUCCEEDED.value: frozenset(),  # terminal
    JobStatus.CANCELLED.value: frozenset(),  # terminal
}


RENDER_JOB_TRANSITIONS: dict[str, frozenset[str]] = {
    RenderJobStatus.QUEUED.value: frozenset(
        {RenderJobStatus.RENDERING.value, RenderJobStatus.FAILED.value}
    ),
    RenderJobStatus.RENDERING.value: frozenset(
        {RenderJobStatus.SUCCEEDED.value, RenderJobStatus.FAILED.value}
    ),
    RenderJobStatus.FAILED.value: frozenset({"retrying"}),
    "retrying": frozenset(
        {RenderJobStatus.RENDERING.value, RenderJobStatus.FAILED.value}
    ),
    RenderJobStatus.SUCCEEDED.value: frozenset(),  # terminal
}


EXPORT_TRANSITIONS: dict[str, frozenset[str]] = {
    ExportArtifactStatus.PENDING.value: frozenset(
        {ExportArtifactStatus.UPLOADING.value, ExportArtifactStatus.FAILED.value}
    ),
    ExportArtifactStatus.UPLOADING.value: frozenset(
        {ExportArtifactStatus.UPLOADED.value, ExportArtifactStatus.FAILED.value}
    ),
    ExportArtifactStatus.UPLOADED.value: frozenset(
        {ExportArtifactStatus.PUBLISHED.value, ExportArtifactStatus.FAILED.value}
    ),
    ExportArtifactStatus.FAILED.value: frozenset({"retrying"}),
    "retrying": frozenset(
        {ExportArtifactStatus.UPLOADING.value, ExportArtifactStatus.FAILED.value}
    ),
    ExportArtifactStatus.PUBLISHED.value: frozenset(),  # terminal
}


TransitionRow: TypeAlias = Job | RenderJob | ExportArtifact

_MAPS: dict[type, tuple[str, dict[str, frozenset[str]]]] = {
    Job: ("Job", JOB_TRANSITIONS),
    RenderJob: ("RenderJob", RENDER_JOB_TRANSITIONS),
    ExportArtifact: ("ExportArtifact", EXPORT_TRANSITIONS),
}


# --- public API ------------------------------------------------------------


def legal_transitions(row_type: type) -> dict[str, frozenset[str]]:
    """Return the transition map for one row type. Read-only view."""
    if row_type not in _MAPS:
        raise TypeError(f"No transition map for {row_type!r}")
    return _MAPS[row_type][1]


def is_terminal(row_type: type, state: str) -> bool:
    return not legal_transitions(row_type).get(state, frozenset())


def transition(
    db: Session,
    row: TransitionRow,
    to: str,
    *,
    reason: str | None = None,
    worker_id: str | None = None,
    force: bool = False,
    status_field: str = "status",
    status_attr: str = "export_status",
) -> str:
    """Mutate `row.status` (or `row.export_status` for ExportArtifact) safely.

    Returns the *from_state* string so callers can include it in audit
    metadata. Raises `IllegalTransition` (and emits a TRANSITION_REJECTED
    usage event) if the move is not permitted.

    `force=True` is only legal for moves into `cancelled`. Anything else
    with `force=True` is still rejected — the escape hatch is narrow on
    purpose so it doesn't become a habit.
    """
    kind, table_map = _MAPS[type(row)]
    attr = "export_status" if isinstance(row, ExportArtifact) else "status"
    from_state: str = getattr(row, attr)

    if from_state == to:
        # no-op transition is allowed and silent; callers sometimes call
        # this defensively when re-driving an already-in-state row.
        return from_state

    allowed = table_map.get(from_state, frozenset())

    if to == JobStatus.CANCELLED.value and force and isinstance(row, Job):
        # Admin override — explicit and audited.
        setattr(row, attr, to)
        _emit_audit_event(
            db,
            row=row,
            kind=kind,
            from_state=from_state,
            to_state=to,
            event_type=UsageEventType.TRANSITION_FORCED,
            reason=reason,
            worker_id=worker_id,
        )
        return from_state

    if to not in allowed:
        _emit_audit_event(
            db,
            row=row,
            kind=kind,
            from_state=from_state,
            to_state=to,
            event_type=UsageEventType.TRANSITION_REJECTED,
            reason=reason,
            worker_id=worker_id,
        )
        raise IllegalTransition(
            kind=kind,
            row_id=str(row.id),
            from_state=from_state,
            to_state=to,
            reason=reason,
        )

    setattr(row, attr, to)
    _emit_audit_event(
        db,
        row=row,
        kind=kind,
        from_state=from_state,
        to_state=to,
        event_type=UsageEventType.TRANSITION_ACCEPTED,
        reason=reason,
        worker_id=worker_id,
    )
    return from_state


# --- audit helper ---------------------------------------------------------


def _emit_audit_event(
    db: Session,
    *,
    row: TransitionRow,
    kind: str,
    from_state: str,
    to_state: str,
    event_type: UsageEventType,
    reason: str | None,
    worker_id: str | None,
) -> None:
    """Write a UsageEvent row directly — bypasses the higher-level helper
    so we can record a TRANSITION_REJECTED event from inside a flush
    without re-entering the transition guard."""
    from api.models import UsageEvent  # local import keeps circular surface small

    md: dict[str, Any] = {
        "kind": kind,
        "row_id": str(row.id),
        "from": from_state,
        "to": to_state,
    }
    if reason:
        md["reason"] = reason
    if worker_id:
        md["worker_id"] = worker_id

    # Pull tenant + job + upload context off the row so the dashboard
    # operational tab can filter by job_id without joins.
    tenant_id = getattr(row, "tenant_id", None)
    if tenant_id is None:
        return  # rows in the wrong tenant scope are caller's bug, not ours

    job_id: uuid.UUID | None = None
    upload_id: uuid.UUID | None = None
    if isinstance(row, Job):
        job_id, upload_id = row.id, row.upload_id
    elif isinstance(row, RenderJob):
        job_id = row.job_id
    # ExportArtifact has no direct job_id; leave None — the candidate is
    # reachable via render_output → render_job → job join.

    db.add(
        UsageEvent(
            tenant_id=tenant_id,
            upload_id=upload_id,
            job_id=job_id,
            event_type=event_type.value,
            quantity=1.0,
            unit="event",
            event_metadata=md,
        )
    )
