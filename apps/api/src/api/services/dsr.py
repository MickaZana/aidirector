"""Data Subject Rights (DSR) — GDPR compliance automation.

Handles:
  1. Data deletion requests with 30-day grace period
  2. Data export requests (ZIP of all user data)
  3. Automatic hard-deletion after grace period expires

Design:
  - Grace period: when a deletion is requested, the tenant's `settings` dict
    gets a `deletion_requested_at` timestamp. All services continue to work
    during the grace period. After 30 days, `execute_pending_deletions()`
    hard-deletes everything.
  - Cascade: thanks to `ON DELETE CASCADE` in the DB schema, deleting a
    tenant cascades to all its Uploads, Jobs, Scenes, ClipCandidates,
    DirectorPlans, RenderJobs, RenderOutputs, ExportArtifacts, UsageEvents,
    EngagementEvents, PerformanceFeatureSets, RankingSnapshots, etc.
  - R2 cleanup: before deleting the tenant row, we iterate all Uploads and
    delete their R2 objects (source videos + rendered outputs + sidecars).
  - Export: all user data is gathered as a structured JSON document with
    provenance metadata so the user can verify authenticity.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import (
    ClipCandidate,
    DirectorPlan,
    ExportArtifact,
    Job,
    PlanCorrection,
    RenderJob,
    RenderOutput,
    Scene,
    Tenant,
    Upload,
    UsageEvent,
    User,
)

log = logging.getLogger(__name__)

# Grace period before hard-deletion (configurable via env or settings).
_GRACE_DAYS = 30


# ---------------------------------------------------------------------------
# Deletion lifecycle
# ---------------------------------------------------------------------------


def request_tenant_deletion(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    requested_by_user_id: uuid.UUID | None = None,
    grace_days: int = _GRACE_DAYS,
) -> dict:
    """Request deletion of a tenant and all associated data.

    During the grace period, the tenant can still use the service and can
    cancel the deletion request. After `grace_days`, the tenant and all
    data are hard-deleted.

    Returns the deletion schedule info.
    """
    tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
    if tenant is None:
        raise ValueError(f"Tenant {tenant_id} not found")

    now = datetime.now(timezone.utc)
    scheduled_for = now + timedelta(days=grace_days)

    settings = dict(tenant.settings or {})
    settings["deletion_requested_at"] = now.isoformat()
    settings["deletion_scheduled_for"] = scheduled_for.isoformat()
    settings["deletion_requested_by"] = str(requested_by_user_id) if requested_by_user_id else None
    settings["deletion_cancelled"] = False
    tenant.settings = settings
    db.flush()

    log.warning(
        "DSR: deletion requested for tenant=%s scheduled=%s",
        tenant_id,
        scheduled_for.isoformat(),
    )
    return {
        "tenant_id": str(tenant_id),
        "deletion_requested_at": now.isoformat(),
        "deletion_scheduled_for": scheduled_for.isoformat(),
        "grace_days": grace_days,
        "message": (
            f"Deletion scheduled for {scheduled_for.strftime('%Y-%m-%d')}. "
            f"Your data will be permanently deleted after this date. "
            f"You can cancel this request before then."
        ),
    }


def cancel_tenant_deletion(db: Session, *, tenant_id: uuid.UUID) -> dict:
    """Cancel a pending deletion request."""
    tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
    if tenant is None:
        raise ValueError(f"Tenant {tenant_id} not found")

    settings = dict(tenant.settings or {})
    if "deletion_requested_at" not in settings:
        return {
            "tenant_id": str(tenant_id),
            "message": "No pending deletion request found.",
        }

    settings["deletion_cancelled"] = True
    settings["deletion_cancelled_at"] = datetime.now(timezone.utc).isoformat()
    tenant.settings = settings
    db.flush()

    log.warning("DSR: deletion cancelled for tenant=%s", tenant_id)
    return {
        "tenant_id": str(tenant_id),
        "message": "Deletion request has been cancelled. Your data will be preserved.",
    }


def execute_pending_deletions(db: Session, *, dry_run: bool = False) -> list[dict]:
    """Hard-delete all tenants whose grace period has expired.

    Called by a daily cron. When `dry_run=True`, only reports what would
    be deleted without actually deleting.

    Returns a list of deletion results.
    """
    now = datetime.now(timezone.utc)
    results: list[dict] = []

    tenants = db.execute(select(Tenant)).scalars().all()
    for tenant in tenants:
        settings = tenant.settings or {}
        requested_str = settings.get("deletion_requested_at")
        cancelled = settings.get("deletion_cancelled", False)
        if not requested_str or cancelled:
            continue

        try:
            requested_at = datetime.fromisoformat(requested_str)
        except (ValueError, TypeError):
            continue

        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=timezone.utc)

        if now - requested_at < timedelta(days=_GRACE_DAYS):
            continue  # grace period not yet expired

        if dry_run:
            results.append(
                {
                    "tenant_id": str(tenant.id),
                    "slug": tenant.slug,
                    "action": "would_delete",
                }
            )
            continue

        # Hard-delete: R2 cleanup first, then DB cascade
        try:
            _cleanup_r2_for_tenant(db, tenant.id)
        except Exception:
            log.exception(
                "DSR: R2 cleanup failed for tenant=%s, proceeding with DB delete", tenant.id
            )

        # Log the deletion
        log.warning("DSR: executing hard-delete for tenant=%s slug=%s", tenant.id, tenant.slug)

        # Delete the tenant — ON DELETE CASCADE handles everything else
        db.delete(tenant)
        db.flush()

        results.append(
            {
                "tenant_id": str(tenant.id),
                "slug": tenant.slug,
                "action": "deleted",
            }
        )

    return results


# ---------------------------------------------------------------------------
# Data export
# ---------------------------------------------------------------------------


def export_tenant_data(db: Session, *, tenant_id: uuid.UUID) -> dict:
    """Gather ALL user data for a tenant into a structured document.

    Returns a dict suitable for JSON serialization or ZIP packaging.
    """
    tenant = db.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()
    if tenant is None:
        raise ValueError(f"Tenant {tenant_id} not found")

    users = db.execute(select(User).where(User.tenant_id == tenant.id)).scalars().all()
    uploads = (
        db.execute(
            select(Upload).where(Upload.tenant_id == tenant.id).order_by(Upload.created_at.asc())
        )
        .scalars()
        .all()
    )
    upload_ids = [u.id for u in uploads]

    jobs = (
        db.execute(select(Job).where(Job.tenant_id == tenant.id).order_by(Job.created_at.asc()))
        .scalars()
        .all()
        if upload_ids
        else []
    )
    job_ids = [j.id for j in jobs]

    scenes = (
        db.execute(select(Scene).where(Scene.job_id.in_(job_ids)).order_by(Scene.t_start.asc()))
        .scalars()
        .all()
        if job_ids
        else []
    )

    candidates = (
        db.execute(select(ClipCandidate).where(ClipCandidate.job_id.in_(job_ids))).scalars().all()
        if job_ids
        else []
    )

    plans = (
        db.execute(select(DirectorPlan).where(DirectorPlan.job_id.in_(job_ids))).scalars().all()
        if job_ids
        else []
    )

    render_jobs = (
        db.execute(select(RenderJob).where(RenderJob.job_id.in_(job_ids))).scalars().all()
        if job_ids
        else []
    )

    render_outputs = (
        db.execute(select(RenderOutput).where(RenderOutput.tenant_id == tenant.id)).scalars().all()
    )

    exports = (
        db.execute(select(ExportArtifact).where(ExportArtifact.tenant_id == tenant.id))
        .scalars()
        .all()
    )

    corrections = (
        db.execute(select(PlanCorrection).where(PlanCorrection.tenant_id == tenant.id))
        .scalars()
        .all()
    )

    usage_events = (
        db.execute(select(UsageEvent).where(UsageEvent.tenant_id == tenant.id)).scalars().all()
    )

    export_data = {
        "export_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "schema_version": "1",
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
        },
        "account": {
            "tenant": {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "name": tenant.name,
                "plan": tenant.plan,
                "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            },
            "users": [
                {
                    "id": str(u.id),
                    "clerk_user_id": u.clerk_user_id,
                    "email": u.email,
                    "role": u.role,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
        },
        "uploads": [
            {
                "id": str(u.id),
                "filename": u.filename,
                "bytes": u.bytes,
                "duration_s": u.duration_s,
                "sport": u.sport,
                "status": u.status,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in uploads
        ],
        "jobs": [
            {
                "id": str(j.id),
                "upload_id": str(j.upload_id),
                "intent": j.intent,
                "status": j.status,
                "error": j.error,
                "cost_budget_cents": j.cost_budget_cents,
                "cost_actual_cents": j.cost_actual_cents,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ],
        "scenes": [
            {
                "id": str(s.id),
                "job_id": str(s.job_id),
                "t_start": s.t_start,
                "t_end": s.t_end,
                "kind": s.kind,
                "intensity": s.intensity,
                "importance": s.importance,
            }
            for s in scenes
        ],
        "clip_candidates": [
            {
                "id": str(c.id),
                "job_id": str(c.job_id),
                "t_start": c.t_start,
                "t_end": c.t_end,
                "confidence_score": c.confidence_score,
                "quality_score": c.quality_score,
                "rationale": c.rationale,
            }
            for c in candidates
        ],
        "director_plans": [
            {
                "id": str(p.id),
                "job_id": str(p.job_id),
                "model": p.model,
                "prompt_version": p.prompt_version,
                "plan_summary": {
                    "candidates": len(p.plan_json.get("selected_candidates", [])),
                    "variants": sum(
                        len(c.get("variants", []))
                        for c in p.plan_json.get("selected_candidates", [])
                    ),
                },
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plans
        ],
        "renders": [
            {
                "id": str(r.id),
                "job_id": str(r.job_id),
                "candidate_id": str(r.candidate_id),
                "pipeline": r.pipeline,
                "platform": r.platform,
                "status": r.status,
                "error": r.error,
                "cost_cents": r.cost_cents,
                "gpu_seconds": r.gpu_seconds,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in render_jobs
        ],
        "exports": [
            {
                "id": str(e.id),
                "render_output_id": str(e.render_output_id),
                "platform": e.platform,
                "status": e.export_status,
                "content_hash": e.content_hash,
                "export_hash": e.export_hash,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in exports
        ],
        "corrections": [
            {
                "id": str(c.id),
                "job_id": str(c.job_id),
                "correction_type": c.correction_type,
                "rationale": c.rationale,
                "applied_at": c.applied_at.isoformat() if c.applied_at else None,
            }
            for c in corrections
        ],
        "usage_events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "quantity": e.quantity,
                "unit": e.unit,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in usage_events
        ],
    }

    return export_data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cleanup_r2_for_tenant(db: Session, tenant_id: uuid.UUID) -> None:
    """Delete all R2 objects belonging to a tenant.

    Iterates Uploads and ExportArtifacts, deleting their R2 keys.
    Failures are logged but do not block the DB cascade delete.
    """
    try:
        from api.services import r2 as r2_svc

        if not r2_svc.is_r2_configured():
            log.warning("DSR: R2 not configured, skipping storage cleanup for tenant=%s", tenant_id)
            return

        # Collect all R2 keys
        keys: list[str] = []

        uploads = db.execute(select(Upload).where(Upload.tenant_id == tenant_id)).scalars().all()
        for u in uploads:
            if u.r2_key:
                keys.append(u.r2_key)

        exports = (
            db.execute(select(ExportArtifact).where(ExportArtifact.tenant_id == tenant_id))
            .scalars()
            .all()
        )
        for e in exports:
            if e.storage_uri:
                # storage_uri may be "r2://bucket/key" or "local://path"
                if e.storage_uri.startswith("r2://"):
                    keys.append(e.storage_uri.replace("r2://", ""))

        for key in keys:
            try:
                r2_svc.delete_object(key)
                log.info("DSR: deleted R2 key=%s for tenant=%s", key, tenant_id)
            except Exception:
                log.warning("DSR: failed to delete R2 key=%s for tenant=%s", key, tenant_id)
    except Exception:
        log.exception("DSR: R2 cleanup error for tenant=%s", tenant_id)
