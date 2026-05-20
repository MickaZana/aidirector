"""Persist a SceneAnalysisResult to the scenes table for a given job.

Used by:
- workers.scene_analysis_worker (after Modal-side analysis completes)
- the phase-2 local probe (drives the same path without Modal)

Emits ANALYSIS_COMPLETED + CANDIDATE_CREATED usage events in the same
transaction so completion and event-log are atomic.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from api.models import Job, JobStatus, Scene, UsageEventType
from api.services.intel.capability_registry import SceneAnalysisResult
from api.services.state_transitions import transition
from api.services.usage_events import emit_usage_event


def persist_scene_analysis(
    db: Session,
    *,
    job: Job,
    result: SceneAnalysisResult,
) -> list[Scene]:
    """Write one Scene row per record + mark job succeeded + emit usage event."""
    rows: list[Scene] = []
    for record in result.scenes:
        row = Scene(
            id=uuid.uuid4(),
            job_id=job.id,
            tenant_id=job.tenant_id,
            t_start=record.t_start,
            t_end=record.t_end,
            kind=record.kind,
            arc_position=record.arc_position,
            intensity=record.intensity,
            importance=record.importance,
            signals=record.signals,
        )
        db.add(row)
        rows.append(row)
    db.flush()

    # Drive job through the state guard. If the job hadn't been
    # transitioned into RUNNING first (e.g. a probe seeded it queued and
    # we're going straight to succeeded), step it through running first.
    if job.status == JobStatus.QUEUED.value:
        transition(db, job, JobStatus.RUNNING.value, reason="analysis_started")
    transition(
        db,
        job,
        JobStatus.SUCCEEDED.value,
        worker_id=job.worker_id,
        reason="analysis_completed",
    )
    job.intel_submodule_sha = result.intel_submodule_sha
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.ANALYSIS_COMPLETED,
        quantity=float(len(rows)),
        unit="scene",
        metadata={
            "intel_submodule_sha": result.intel_submodule_sha,
            "raw_metrics": result.raw_metrics,
        },
    )
    return rows
