"""Persist RenderJob + RenderOutput rows + emit render lifecycle usage events.

Used by:
- workers.render_worker (after the adapter returns)
- the phase-5 local probe (drives the same path without Modal)

Lifecycle:
  1. `start_render_job(...)`  → INSERT RenderJob (status=rendering) + emit RENDER_STARTED
  2. (adapter executes the render)
  3a. on success: `complete_render_job(...)` → UPDATE RenderJob (status=succeeded)
       + INSERT RenderOutput + emit RENDER_COMPLETED
  3b. on failure: `fail_render_job(...)` → UPDATE RenderJob (status=failed)
       + emit JOB_FAILED

This split lets the worker emit RENDER_STARTED before kicking off a long
ffmpeg subprocess, so dashboard queries reflect in-flight work.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.models import Job, RenderJob, RenderJobStatus, RenderOutput, UsageEventType
from api.schemas.render_manifest import RenderManifest
from api.services.intel.render_plan_adapter import RenderExecutionResult
from api.services.state_transitions import transition
from api.services.usage_events import emit_usage_event


def start_render_job(
    db: Session,
    *,
    job: Job,
    manifest: RenderManifest,
    idempotency_key: str | None = None,
    worker_id: str | None = None,
) -> RenderJob:
    """INSERT a RenderJob row (status=queued) then drive it through the
    state guard into RENDERING + emit RENDER_STARTED.

    `idempotency_key` should be supplied by the caller — typically built
    via `services.idempotency.render_idempotency_key(...)`. The UNIQUE
    index on the column means a duplicate worker firing for the same
    (candidate, variant, render_style, plan_version) will raise on commit;
    callers should pre-check with `idempotency.claim_render` and skip.
    """
    row = RenderJob(
        id=uuid.UUID(manifest.render_job_id),
        job_id=job.id,
        tenant_id=job.tenant_id,
        candidate_id=uuid.UUID(manifest.candidate_id),
        pipeline=manifest.renderer,
        platform=manifest.platform,
        status=RenderJobStatus.QUEUED.value,
        settings={
            "manifest": manifest.model_dump(mode="json"),
        },
        idempotency_key=idempotency_key,
        worker_id=worker_id,
    )
    db.add(row)
    db.flush()

    # Drive queued → rendering through the guard so a stray prior call
    # that already moved this row into a terminal state fails loudly.
    transition(
        db,
        row,
        RenderJobStatus.RENDERING.value,
        worker_id=worker_id,
        reason="start_render_job",
    )
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.RENDER_STARTED,
        unit="render",
        metadata={
            "render_job_id": manifest.render_job_id,
            "candidate_id": manifest.candidate_id,
            "platform": manifest.platform,
            "renderer": manifest.renderer,
            "render_style": manifest.render_style,
        },
    )
    return row


def complete_render_job(
    db: Session,
    *,
    job: Job,
    render_job: RenderJob,
    manifest: RenderManifest,
    result: RenderExecutionResult,
    r2_key: str | None = None,
) -> RenderOutput:
    """UPDATE the RenderJob + INSERT a RenderOutput + emit RENDER_COMPLETED.

    `r2_key` is the eventual cloud-storage key. For Phase 5 local execution
    it's a sentinel `local://<absolute_path>` — Phase 5.5 will replace it
    with a real R2 upload after success.
    """
    if r2_key is None:
        r2_key = f"local://{result.output_path}" if result.output_path else "local://unknown"

    transition(
        db,
        render_job,
        RenderJobStatus.SUCCEEDED.value,
        worker_id=render_job.worker_id,
        reason="render_completed",
    )
    render_job.finished_at = datetime.now(timezone.utc)
    render_job.cost_cents = _estimate_cost_cents(result)
    db.flush()

    output_row = RenderOutput(
        id=uuid.uuid4(),
        render_job_id=render_job.id,
        tenant_id=job.tenant_id,
        r2_key=r2_key,
        aspect_ratio=manifest.aspect_ratio,
        duration_s=result.duration_s,
        bytes=result.bytes,
        output_metadata={
            "platform": manifest.platform,
            "renderer": manifest.renderer,
            "elapsed_seconds": result.elapsed_seconds,
            "command_argv0": (result.command[0] if result.command else None),
            "command_arglen": len(result.command),
        },
    )
    db.add(output_row)
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.RENDER_COMPLETED,
        quantity=result.duration_s or 0.0,
        unit="clip_seconds",
        estimated_cost_cents=render_job.cost_cents,
        metadata={
            "render_job_id": manifest.render_job_id,
            "candidate_id": manifest.candidate_id,
            "platform": manifest.platform,
            "renderer": manifest.renderer,
            "bytes": result.bytes,
        },
    )
    return output_row


def fail_render_job(
    db: Session,
    *,
    job: Job,
    render_job: RenderJob,
    manifest: RenderManifest,
    result: RenderExecutionResult,
) -> None:
    transition(
        db,
        render_job,
        RenderJobStatus.FAILED.value,
        worker_id=render_job.worker_id,
        reason=result.error or "unknown render failure",
    )
    render_job.finished_at = datetime.now(timezone.utc)
    render_job.error = result.error or "unknown render failure"
    db.flush()

    emit_usage_event(
        db,
        tenant_id=job.tenant_id,
        upload_id=job.upload_id,
        job_id=job.id,
        event_type=UsageEventType.JOB_FAILED,
        unit="render",
        metadata={
            "render_job_id": manifest.render_job_id,
            "candidate_id": manifest.candidate_id,
            "platform": manifest.platform,
            "renderer": manifest.renderer,
            "error": result.error,
            "stderr_tail": result.stderr_tail,
        },
    )


def _estimate_cost_cents(result: RenderExecutionResult) -> int:
    """Per-render cost guess. Tuned later from Modal billing telemetry."""
    elapsed = max(0.0, float(result.elapsed_seconds))
    base = 1
    return base + int(elapsed)  # 1¢ floor + 1¢ per second of compute
