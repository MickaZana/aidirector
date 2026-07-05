"""Data Subject Rights (DSR) router — GDPR compliance endpoints.

Provides self-service endpoints for:
  - Requesting account deletion (with 30-day grace period)
  - Cancelling a pending deletion request
  - Checking deletion status
  - Exporting all personal data (GDPR Article 20)

All endpoints require authentication (tenant scope). The tenant can only
manage their own data.

For admins:
  - POST /api/v1/dsr/execute-pending — Execute all pending deletions whose
    grace period has expired (also runs automatically via Modal cron).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import Tenant

log = logging.getLogger(__name__)

router = APIRouter(prefix="/dsr", tags=["dsr"])


# ── Schemas ─────────────────────────────────────────────────────────────────


class DeletionRequestOut(BaseModel):
    """Response after requesting account deletion."""

    tenant_id: str
    deletion_requested_at: str
    deletion_scheduled_for: str
    grace_days: int
    message: str


class DeletionCancelOut(BaseModel):
    """Response after cancelling a pending deletion."""

    tenant_id: str
    message: str


class DeletionStatusOut(BaseModel):
    """Current deletion request status."""

    tenant_id: str
    deletion_requested: bool = False
    deletion_requested_at: str | None = None
    deletion_scheduled_for: str | None = None
    deletion_cancelled: bool = False
    grace_days: int = 30
    days_remaining: int | None = None


class DataExportOut(BaseModel):
    """Response containing the exported data."""

    generated_at: str
    schema_version: str
    account: dict
    uploads: list = []
    jobs: list = []
    scenes: list = []
    clip_candidates: list = []
    director_plans: list = []
    renders: list = []
    exports: list = []
    corrections: list = []
    usage_events: list = []


class ExecutePendingOut(BaseModel):
    """Result of executing pending deletions."""

    deleted: list[dict]
    total: int


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/deletion", response_model=DeletionRequestOut, status_code=status.HTTP_202_ACCEPTED)
def request_deletion(
    tenant: TenantRow,
    db: DbSession,
) -> DeletionRequestOut:
    """Request deletion of your account and all associated data.

    A 30-day grace period applies. During this time you can still use the
    service and can cancel the request. After 30 days, all data is
    permanently deleted.
    """
    from api.services.dsr import request_tenant_deletion

    result = request_tenant_deletion(db, tenant_id=tenant.id)
    return DeletionRequestOut(
        tenant_id=result["tenant_id"],
        deletion_requested_at=result["deletion_requested_at"],
        deletion_scheduled_for=result["deletion_scheduled_for"],
        grace_days=result["grace_days"],
        message=result["message"],
    )


@router.delete("/deletion", response_model=DeletionCancelOut)
def cancel_deletion(
    tenant: TenantRow,
    db: DbSession,
) -> DeletionCancelOut:
    """Cancel a pending deletion request."""
    from api.services.dsr import cancel_tenant_deletion

    result = cancel_tenant_deletion(db, tenant_id=tenant.id)
    return DeletionCancelOut(
        tenant_id=result["tenant_id"],
        message=result["message"],
    )


@router.get("/deletion", response_model=DeletionStatusOut)
def get_deletion_status(
    tenant: TenantRow,
    db: DbSession,
) -> DeletionStatusOut:
    """Check the status of a pending deletion request."""
    row = db.execute(select(Tenant).where(Tenant.id == tenant.id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")

    settings = row.settings or {}
    requested_str = settings.get("deletion_requested_at")
    cancelled = settings.get("deletion_cancelled", False)
    grace_days = 30

    if not requested_str:
        return DeletionStatusOut(
            tenant_id=str(tenant.id),
            deletion_requested=False,
            grace_days=grace_days,
        )

    requested_at = datetime.fromisoformat(requested_str)
    if requested_at.tzinfo is None:
        requested_at = requested_at.replace(tzinfo=timezone.utc)

    scheduled_for = requested_at + timedelta(days=grace_days)
    now = datetime.now(timezone.utc)
    days_remaining = max(0, (scheduled_for - now).days)

    return DeletionStatusOut(
        tenant_id=str(tenant.id),
        deletion_requested=True,
        deletion_requested_at=requested_str,
        deletion_scheduled_for=scheduled_for.isoformat(),
        deletion_cancelled=cancelled,
        grace_days=grace_days,
        days_remaining=days_remaining if not cancelled else None,
    )


@router.post("/export", response_model=DataExportOut)
def export_data(
    tenant: TenantRow,
    db: DbSession,
) -> DataExportOut:
    """Export all your personal data (GDPR Article 20).

    Returns a structured JSON document containing all account information,
    uploads, jobs, clips, renders, exports, corrections, and usage events.
    """
    from api.services.dsr import export_tenant_data

    data = export_tenant_data(db, tenant_id=tenant.id)
    return DataExportOut(
        generated_at=data["export_metadata"]["generated_at"],
        schema_version=data["export_metadata"]["schema_version"],
        account=data["account"],
        uploads=data["uploads"],
        jobs=data["jobs"],
        scenes=data["scenes"],
        clip_candidates=data["clip_candidates"],
        director_plans=data["director_plans"],
        renders=data["renders"],
        exports=data["exports"],
        corrections=data["corrections"],
        usage_events=data["usage_events"],
    )


@router.post("/execute-pending", response_model=ExecutePendingOut)
def execute_pending_deletions(
    tenant: TenantRow,
    db: DbSession,
    dry_run: bool = True,
) -> ExecutePendingOut:
    """Execute pending deletions whose grace period has expired.

    By default runs in dry_run mode. Set `dry_run=false` for actual deletion.
    Also runs automatically via Modal cron daily.
    """
    from api.services.dsr import execute_pending_deletions

    results = execute_pending_deletions(db, dry_run=dry_run)
    return ExecutePendingOut(deleted=results, total=len(results))
