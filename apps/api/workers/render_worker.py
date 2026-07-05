"""RQ render worker — pops one render job payload and executes it.

Called by RQ when a job is dequeued from q:render-cpu. The function is
registered by name so Modal workers and local `rq worker` processes both
resolve it the same way.

Payload contract (dict):
    job_id      str  — UUID of the Job row that owns these renders
    source_uri  str  — R2 URL or local path ffmpeg can read directly
    source_path str  — optional absolute local path for ASR enrichment;
                       omit when running on Modal (file not on worker disk)
    source_duration_s  float — Upload.duration_s for viral-title position logic
    srt_dir     str  — optional directory for per-clip SRT files; omit on Modal

Returns a summary dict (stored in rq Job.result for polling).
"""
from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select

import sentry_sdk

from api.db import SessionLocal
from api.models import Job, DirectorPlan as DirectorPlanRow, Upload
from api.schemas.director_plan import DirectorPlan as DirectorPlanContract
from api.services.idempotency import claim_render, render_idempotency_key
from api.services.intel.render_plan_adapter import render_clip
from api.services.render_manifest_builder import build_manifests
from api.services.render_output_persistence import (
    complete_render_job,
    fail_render_job,
    start_render_job,
)

log = logging.getLogger(__name__)


def execute_render_job(payload: dict) -> dict:
    """Entry point for RQ. `payload` matches the contract in the module docstring."""
    from api.config import get_settings
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env)

    job_id = uuid.UUID(payload["job_id"])
    source_uri: str = payload["source_uri"]
    source_path_str: str | None = payload.get("source_path")
    source_duration_s: float | None = payload.get("source_duration_s")
    srt_dir_str: str | None = payload.get("srt_dir")

    source_path = Path(source_path_str) if source_path_str else None
    srt_output_dir = Path(srt_dir_str) if srt_dir_str else None

    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured — cannot open DB session")

    results: list[dict] = []
    with SessionLocal() as db:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        plan_row = db.execute(
            select(DirectorPlanRow)
            .where(DirectorPlanRow.job_id == job_id)
            .order_by(DirectorPlanRow.created_at.desc())
        ).scalar_one_or_none()
        if plan_row is None:
            raise ValueError(f"No DirectorPlan found for job {job_id}")

        plan = DirectorPlanContract.model_validate(plan_row.plan_json)

        upload = db.execute(
            select(Upload).where(Upload.id == job.upload_id)
        ).scalar_one_or_none()
        tenant_slug = str(job.tenant_id)[:8]  # fallback slug; real slug comes from Tenant row

        # Use a temp dir for SRTs when caller doesn't provide one.
        _tmp_ctx = None
        if srt_output_dir is None and source_path is not None:
            _tmp_ctx = tempfile.TemporaryDirectory(prefix="aidirector_srt_")
            srt_output_dir = Path(_tmp_ctx.name)

        try:
            build_result = build_manifests(
                plan=plan,
                source_uri=source_uri,
                tenant_id=str(job.tenant_id),
                tenant_slug=tenant_slug,
                source_path=source_path,
                source_duration_s=source_duration_s or (upload.duration_s if upload else None),
                srt_output_dir=srt_output_dir,
            )
        finally:
            if _tmp_ctx is not None:
                _tmp_ctx.cleanup()
                srt_output_dir = None

        log.info(
            "render_worker: job=%s manifests=%d unrenderable=%d",
            job_id, len(build_result.manifests), len(build_result.unrenderable),
        )

        output_dir = Path(tempfile.mkdtemp(prefix="aidirector_render_"))

        for manifest in build_result.manifests:
            idem_key = render_idempotency_key(
                candidate_id=manifest.candidate_id,
                variant_id=manifest.render_job_id,  # unique per manifest build
                render_style=manifest.render_style,
                plan_version=plan.version if hasattr(plan, "version") else "1",
            )
            existing = claim_render(db, idempotency_key=idem_key)
            if existing is not None:
                log.info("render_worker: idempotency replay render_job=%s", existing.id)
                results.append({"render_job_id": str(existing.id), "status": "replayed"})
                continue

            render_job_row = start_render_job(
                db, job=job, manifest=manifest, idempotency_key=idem_key
            )
            db.commit()

            result = render_clip(manifest, output_dir=output_dir, timeout_s=300.0)

            if result.status == "succeeded":
                r2_key = f"local://{result.output_path}"
                complete_render_job(
                    db, job=job, render_job=render_job_row,
                    manifest=manifest, result=result, r2_key=r2_key,
                )
            else:
                fail_render_job(db, job=job, render_job=render_job_row,
                                manifest=manifest, result=result)

            db.commit()
            log.info(
                "render_worker: candidate=%s status=%s elapsed=%.1fs",
                manifest.candidate_id, result.status, result.elapsed_seconds,
            )
            results.append({
                "render_job_id": manifest.render_job_id,
                "candidate_id": manifest.candidate_id,
                "status": result.status,
                "elapsed_seconds": result.elapsed_seconds,
                "error": result.error,
            })

    return {"job_id": str(job_id), "renders": results}
