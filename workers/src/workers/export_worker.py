"""Export worker — Modal-side wrapper over the export artifact builder.

Zero business logic. Receives a RenderOutput id + platform; uploads the
rendered file to storage via `r2.put_local_file`, builds an
ExportArtifact identity, persists it, returns the result.

Future-proof: when real R2 credentials land, `put_local_file` switches to
R2 transparently. The worker, builder, persistence, and probe all stay
identical.
"""

from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def create_export_artifact_fixture(
    render_output_id: str,
    candidate_id: str,
    tenant_slug: str,
    platform: str,
    local_source_path: str,
    export_version: int = 1,
) -> dict:
    """Phase 6 fixture path: caller supplies an existing local render path,
    we hash + upload + persist. Returns the ExportArtifact row as a dict.
    """
    import uuid as _uuid
    from pathlib import Path

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import Job, RenderJob, RenderOutput
    from api.services.export_artifact_builder import build_export_artifact
    from api.services.export_persistence import persist_export_artifact
    from api.services.r2 import put_local_file, parse_storage_uri

    assert engine is not None, "DATABASE_URL must be set for export worker"

    with Session(engine) as db:
        ro = db.execute(
            select(RenderOutput).where(RenderOutput.id == _uuid.UUID(render_output_id))
        ).scalar_one_or_none()
        if ro is None:
            raise ValueError(f"RenderOutput {render_output_id} not found")

        # Resolve the owning job via RenderJob → Job chain, NOT by
        # fetching the tenant's most-recent job (which can be wrong when
        # a tenant has multiple jobs in flight).
        rj = db.execute(
            select(RenderJob).where(RenderJob.id == ro.render_job_id)
        ).scalar_one_or_none()
        if rj is None:
            raise ValueError(
                f"RenderJob {ro.render_job_id} not found for RenderOutput {render_output_id}"
            )
        job = db.execute(select(Job).where(Job.id == rj.job_id)).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {rj.job_id} not found for RenderOutput {render_output_id}")

        inputs = build_export_artifact(
            render_output=ro,
            tenant_slug=tenant_slug,
            candidate_id=_uuid.UUID(candidate_id),
            platform=platform,
            local_source_path=Path(local_source_path),
            export_version=export_version,
        )

        # Transport the bytes. In local mode this copies to the mirror;
        # in R2 mode this uploads to the bucket. Either way the storage_uri
        # in `inputs` already matches the destination.
        scheme, key = parse_storage_uri(inputs.storage_uri)
        if scheme == "local":
            # parse_storage_uri returned the local absolute path; rebuild
            # the storage-key from the tenant prefix structure.
            from api.services.r2 import export_key

            key = export_key(str(ro.tenant_id), str(inputs.export_id), inputs.filename)
        put_local_file(Path(local_source_path), key)

        row = persist_export_artifact(db, job=job, render_output=ro, inputs=inputs)
        db.commit()
        return {
            "id": str(row.id),
            "render_output_id": str(row.render_output_id),
            "platform": row.platform,
            "export_hash": row.export_hash,
            "content_hash": row.content_hash,
            "content_bytes": row.content_bytes,
            "storage_uri": row.storage_uri,
            "filename": row.filename,
            "export_status": row.export_status,
        }
