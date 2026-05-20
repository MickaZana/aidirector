"""Idempotency keys + claim semantics for render + export.

Two distinct keys, two distinct purposes:

  - **render_idempotency_key** = sha256(candidate_id|variant_id|render_style|version)
    The same SelectedCandidate + Variant + render_style at the same
    DirectorPlan version is the same render. Re-running the same
    fixture produces the same key, the DB enforces uniqueness, and
    `claim_render(...)` returns the *existing* RenderJob instead of
    inserting a duplicate.

  - **export_idempotency_key** = sha256(render_output_id|platform|export_version)
    This is identical to `ExportArtifact.export_hash` — it's already
    UNIQUE in the schema (see migration 0002). We expose it here so
    workers can dedupe *before* they upload bytes, not after.

Replay protection:

  When `claim_render(...)` finds an existing row, the caller MUST treat
  the work as already-done: emit an `IDEMPOTENCY_REPLAY` audit event,
  log the original render_job_id, and return without re-uploading bytes.

  When `claim_export(...)` finds an existing row, the caller MUST NOT
  uploadre a different blob — uploading a different blob under the same
  storage_uri would corrupt the content_hash invariant. Either re-use
  the existing artifact or bump `export_version` to get a fresh key.
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import ExportArtifact, RenderJob

# Version on the render-key shape itself, not the schema. Bump if we
# ever change WHICH fields contribute to the key (rare; backfill required).
RENDER_KEY_VERSION = "v1"
# Export-key formula is locked to the historical `export_hash` builder
# (no version suffix) so a re-run of the export builder for an existing
# (render_output, platform, version) produces the SAME hash as the
# pre-existing row in `exports.export_hash`. No EXPORT_KEY_VERSION
# constant on purpose.


# --- key builders (pure) ---------------------------------------------------


def render_idempotency_key(
    *,
    candidate_id: str | uuid.UUID,
    variant_id: str,
    render_style: str,
    plan_version: str,
) -> str:
    """Deterministic key for one (candidate, variant, style, plan-version)."""
    raw = f"{candidate_id}|{variant_id}|{render_style}|{plan_version}|{RENDER_KEY_VERSION}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def export_idempotency_key(
    *,
    render_output_id: str | uuid.UUID,
    platform: str,
    export_version: int,
) -> str:
    """Identical formula to ExportArtifact.export_hash — single source of truth.

    Lockstep with `services/export_artifact_builder.build_export_artifact`:

        sha256(f"{render_output_id}|{platform}|{export_version}")

    If we ever bump this formula, both call sites change in one commit
    and a migration backfills `exports.export_hash` for existing rows.
    """
    raw = f"{render_output_id}|{platform}|{export_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --- claim semantics ------------------------------------------------------


def claim_render(
    db: Session,
    *,
    idempotency_key: str,
) -> RenderJob | None:
    """Return the existing RenderJob for this key, or None if free.

    Callers wrap this around their insert path:

        existing = claim_render(db, idempotency_key=key)
        if existing is not None:
            emit_audit_event(IDEMPOTENCY_REPLAY, ...)
            return existing
        row = RenderJob(idempotency_key=key, ...)
        db.add(row)

    The UNIQUE index on `render_jobs.idempotency_key` is the real
    enforcement; this lookup is the friendly path before SQLAlchemy
    would otherwise raise `IntegrityError` on commit.
    """
    return db.execute(
        select(RenderJob).where(RenderJob.idempotency_key == idempotency_key)
    ).scalar_one_or_none()


def claim_export(
    db: Session,
    *,
    export_hash: str,
) -> ExportArtifact | None:
    """Return the existing ExportArtifact for this export_hash, or None.

    `export_hash` is what `export_idempotency_key` produces. The UNIQUE
    index on `exports.export_hash` (from migration 0002) is the enforcement.
    """
    return db.execute(
        select(ExportArtifact).where(ExportArtifact.export_hash == export_hash)
    ).scalar_one_or_none()
