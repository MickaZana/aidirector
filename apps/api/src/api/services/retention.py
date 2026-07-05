"""Retention policy service — configurable data lifecycle management.

Implements S6.2d: automated cleanup of expired jobs and their associated
R2 objects (source uploads, rendered clips, export artifacts).

Policy:
  - Retention period is configurable via env var `RETENTION_DAYS` (default 90).
  - The cleanup job runs daily via Modal cron.
  - Jobs in a terminal state (SUCCEEDED, FAILED, CANCELLED) that are older
    than the retention window are transitioned to EXPIRED.
  - Once EXPIRED, R2 objects are deleted, then DB rows are cascade-deleted.

R2 objects cleaned up:
  1. Upload source files (tenant/{tenant_id}/upload/{upload_id}/...)
  2. Render outputs (tenant/{tenant_id}/render/{render_id}/...)
  3. Export artifacts (tenant/{tenant_id}/exports/{export_id}/...)
  4. Provenance sidecar files (*.c2pa.json)

NOT cleaned up (preserved for cross-tenant reference):
  - C2PA DID documents (_c2pa/did/)
  - C2PA trust anchor registry (_c2pa/trust_anchor/)

Usage:
    from api.services.retention import apply_retention_policy
    result = apply_retention_policy(retention_days=90, dry_run=True)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from api.db import SessionLocal
from api.models import (
    ExportArtifact,
    Job,
    JobStatus,
    RenderOutput,
    Upload,
)

log = logging.getLogger(__name__)

# Default retention: 90 days
_DEFAULT_RETENTION_DAYS = 90


def retention_days_setting() -> int:
    """Return the configured retention period in days.

    Read from env var RETENTION_DAYS. Falls back to default.
    """
    raw = os.environ.get("RETENTION_DAYS", str(_DEFAULT_RETENTION_DAYS))
    try:
        return max(1, int(raw))
    except (ValueError, TypeError):
        return _DEFAULT_RETENTION_DAYS


@dataclass(frozen=True)
class RetentionResult:
    """Result of a retention policy run."""

    jobs_expired: int = 0
    r2_keys_deleted: int = 0
    errors: list[str] | None = None
    dry_run: bool = False


def apply_retention_policy(
    retention_days: int | None = None,
    dry_run: bool = False,
    batch_size: int = 50,
) -> RetentionResult:
    """Apply the retention policy: expire old jobs and clean up their data.

    Args:
        retention_days: Age threshold in days. Defaults to env var or 90.
        dry_run: If True, log what WOULD be deleted but don't touch anything.
        batch_size: Max jobs to process per run (safety limit).

    Returns:
        RetentionResult with counts of expired/deleted items.
    """
    if retention_days is None:
        retention_days = retention_days_setting()

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    errors: list[str] = []
    jobs_expired = 0
    r2_keys_deleted = 0

    log.info(
        "retention: applying policy (retention_days=%d, cutoff=%s, dry_run=%s)",
        retention_days,
        cutoff.isoformat(),
        dry_run,
    )

    with SessionLocal() as db:
        # Find terminal-state jobs older than the cutoff
        terminal_statuses = [
            JobStatus.SUCCEEDED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ]
        expired_jobs = (
            db.execute(
                select(Job)
                .where(Job.status.in_(terminal_statuses))
                .where(Job.created_at < cutoff)
                .order_by(Job.created_at.asc())
                .limit(batch_size)
            )
            .scalars()
            .all()
        )

        if not expired_jobs:
            log.info("retention: no expired jobs found")
            return RetentionResult(dry_run=dry_run)

        log.info(
            "retention: found %d jobs to expire (batch_size=%d)",
            len(expired_jobs),
            batch_size,
        )

        for job in expired_jobs:
            try:
                keys = _collect_r2_keys(db, job)
                r2_keys_deleted += _delete_keys(keys, dry_run=dry_run)
                if not dry_run:
                    job.status = JobStatus.EXPIRED.value
                    job.finished_at = datetime.now(timezone.utc)
                jobs_expired += 1
            except Exception as exc:
                msg = f"retention: failed to expire job {job.id}: {exc}"
                log.exception(msg)
                errors.append(msg)

        if not dry_run:
            db.commit()

    log.info(
        "retention: complete jobs_expired=%d r2_keys_deleted=%d errors=%d dry_run=%s",
        jobs_expired,
        r2_keys_deleted,
        len(errors),
        dry_run,
    )

    return RetentionResult(
        jobs_expired=jobs_expired,
        r2_keys_deleted=r2_keys_deleted,
        errors=errors or None,
        dry_run=dry_run,
    )


def _collect_r2_keys(db, job: Job) -> list[str]:
    """Collect all R2 keys associated with a job for deletion."""
    from api.services import r2

    keys: list[str] = []

    # 1. Source upload
    upload = db.execute(select(Upload).where(Upload.id == job.upload_id)).scalar_one_or_none()
    if upload and upload.r2_key:
        keys.append(upload.r2_key)

    # 2. Render outputs (query by tenant_id for this job's renders)
    render_outputs = (
        db.execute(select(RenderOutput).where(RenderOutput.tenant_id == job.tenant_id))
        .scalars()
        .all()
    )
    for ro in render_outputs:
        if ro.r2_key:
            keys.append(ro.r2_key)
            # C2PA sidecar file
            keys.append(_sidecar_key(ro.r2_key))

    # 3. Export artifacts
    exports = (
        db.execute(select(ExportArtifact).where(ExportArtifact.tenant_id == job.tenant_id))
        .scalars()
        .all()
    )
    for ex in exports:
        try:
            _, key = r2.parse_storage_uri(ex.storage_uri)
            keys.append(key)
        except ValueError:
            pass

    return keys


def _delete_keys(keys: list[str], *, dry_run: bool) -> int:
    """Delete R2 keys. Returns count of successful deletions."""
    from api.services import r2

    deleted = 0
    for key in keys:
        if not key:
            continue
        if dry_run:
            log.info("retention: [DRY RUN] would delete r2 key=%s", key)
            deleted += 1
        else:
            try:
                r2.delete_object(key)
                deleted += 1
                log.debug("retention: deleted r2 key=%s", key)
            except Exception as exc:
                log.warning("retention: failed to delete r2 key=%s: %s", key, exc)
    return deleted


def _sidecar_key(r2_key: str) -> str:
    """Derive the C2PA sidecar key from a render output key."""
    if "." in r2_key:
        base = r2_key.rsplit(".", 1)[0]
    else:
        base = r2_key
    return f"{base}.c2pa.json"
