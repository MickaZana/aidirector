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
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

import sentry_sdk

from api.db import SessionLocal
from api.models import Job, DirectorPlan as DirectorPlanRow, Upload
from api.schemas.director_plan import DirectorPlan as DirectorPlanContract
from api.schemas.provenance_manifest import RenderAssertion
from api.schemas.render_manifest import RenderManifest
from api.services.idempotency import claim_render, render_idempotency_key
from api.services.intel.render_plan_adapter import render_clip, RenderExecutionResult
from api.services.provenance import ProvSigner, assertion_from_manifest
from api.services.render_manifest_builder import build_manifests, ManifestBuildResult
from api.services.render_output_persistence import (
    complete_render_job,
    fail_render_job,
    start_render_job,
)

log = logging.getLogger(__name__)

# Max parallel FFmpeg subprocesses. Determined by CPU cores × I/O wait.
# FFmpeg is primarily I/O-bound during decode (reading source) and encode
# (writing output), so a higher-than-core-count ratio works well.
_MAX_PARALLEL_RENDERS = 6


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

    # ------------------------------------------------------------------
    # 1. Load plan + build all manifests (sequential — fast, I/O-light)
    # ------------------------------------------------------------------
    base_results: list[dict] = []
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

        upload = db.execute(select(Upload).where(Upload.id == job.upload_id)).scalar_one_or_none()
        tenant_slug = str(job.tenant_id)[:8]

        # Use a temp dir for SRTs when caller doesn't provide one.
        _tmp_ctx = None
        if srt_output_dir is None and source_path is not None:
            _tmp_ctx = tempfile.TemporaryDirectory(prefix="aidirector_srt_")
            srt_output_dir = Path(_tmp_ctx.name)

        try:
            build_result: ManifestBuildResult = build_manifests(
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

        job_id_str = str(job_id)
        log.info(
            "render_worker: job=%s manifests=%d unrenderable=%d",
            job_id_str,
            len(build_result.manifests),
            len(build_result.unrenderable),
        )

        # Check idempotency for each manifest (sequential — fast DB lookups)
        idem_keys: list[str | None] = []
        for manifest in build_result.manifests:
            ik = render_idempotency_key(
                candidate_id=manifest.candidate_id,
                variant_id=manifest.render_job_id,
                render_style=manifest.render_style,
                plan_version=plan.version if hasattr(plan, "version") else "1",
            )
            existing = claim_render(db, idempotency_key=ik)
            if existing is not None:
                log.info("render_worker: idempotency replay render_job=%s", existing.id)
                base_results.append(
                    {
                        "render_job_id": str(existing.id),
                        "candidate_id": manifest.candidate_id,
                        "status": "replayed",
                        "elapsed_seconds": 0.0,
                        "error": None,
                    }
                )
                idem_keys.append(None)  # skip this manifest
            else:
                idem_keys.append(ik)

    # Filter to manifests that need actual rendering
    pending_manifests: list[RenderManifest] = []
    pending_keys: list[str] = []
    for manifest, ik in zip(build_result.manifests, idem_keys):
        if ik is not None:
            pending_manifests.append(manifest)
            pending_keys.append(ik)

    if not pending_manifests:
        return {"job_id": job_id_str, "renders": base_results, "parallel": False}

    # ------------------------------------------------------------------
    # 2. Render all pending manifests in parallel via ThreadPoolExecutor
    # ------------------------------------------------------------------
    output_dir = Path(tempfile.mkdtemp(prefix="aidirector_render_"))
    render_tasks: list[dict] = []

    with ThreadPoolExecutor(max_workers=_MAX_PARALLEL_RENDERS) as pool:
        futures = {}
        for manifest in pending_manifests:
            future = pool.submit(
                _render_one_manifest,
                manifest=manifest,
                output_dir=output_dir,
                job_id_str=job_id_str,
            )
            futures[future] = manifest

        for future in as_completed(futures):
            manifest = futures[future]
            try:
                render_tasks.append(future.result())
            except Exception as exc:
                log.exception(
                    "render_worker: parallel render failed candidate=%s", manifest.candidate_id
                )
                render_tasks.append(
                    {
                        "render_job_id": manifest.render_job_id,
                        "candidate_id": manifest.candidate_id,
                        "status": "failed",
                        "elapsed_seconds": 0.0,
                        "error": str(exc),
                    }
                )

    # ------------------------------------------------------------------
    # 3. Persist results (back to sequential — DB writes must be ordered)
    # ------------------------------------------------------------------
    completed_results: list[dict] = []
    with SessionLocal() as db:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found (deleted during render?)")

        for manifest, ik in zip(pending_manifests, pending_keys):
            task = next(
                (t for t in render_tasks if t["candidate_id"] == manifest.candidate_id), None
            )
            if task is None:
                continue

            if task["status"] == "replayed":
                completed_results.append(task)
                continue

            render_job_row = start_render_job(
                db,
                job=job,
                manifest=manifest,
                idempotency_key=ik,
            )
            db.commit()

            # Reconstruct result from task data
            result = RenderExecutionResult(
                render_job_id=manifest.render_job_id,
                candidate_id=manifest.candidate_id,
                status=task["status"],
                output_path=task.get("output_path"),
                bytes=task.get("bytes"),
                duration_s=task.get("duration_s"),
                renderer=manifest.renderer,
                command=task.get("command", []),
                elapsed_seconds=task.get("elapsed_seconds", 0.0),
                error=task.get("error"),
            )

            if result.status == "succeeded" and result.output_path:
                r2_key = f"local://{result.output_path}"
                complete_render_job(
                    db,
                    job=job,
                    render_job=render_job_row,
                    manifest=manifest,
                    result=result,
                    r2_key=r2_key,
                )
                log.info(
                    "render_worker: candidate=%s status=succeeded elapsed=%.1fs",
                    manifest.candidate_id,
                    result.elapsed_seconds,
                )
            else:
                fail_render_job(
                    db,
                    job=job,
                    render_job=render_job_row,
                    manifest=manifest,
                    result=result,
                )
                log.info(
                    "render_worker: candidate=%s status=failed error=%s",
                    manifest.candidate_id,
                    result.error,
                )

            db.commit()
            completed_results.append(task)

    # ------------------------------------------------------------------
    # 4. Record pipeline timing on the Job row
    # ------------------------------------------------------------------
    _record_pipeline_timing(
        job_id=job_id,
        build_result=build_result,
        render_tasks=render_tasks,
        base_results=base_results,
        completed_results=completed_results,
    )

    return {
        "job_id": job_id_str,
        "renders": base_results + completed_results,
        "parallel": len(pending_manifests) > 1,
        "total_renders": len(build_result.manifests),
        "parallel_count": len(pending_manifests),
    }


def _render_one_manifest(
    *,
    manifest: RenderManifest,
    output_dir: Path,
    job_id_str: str,
) -> dict:
    """Execute a single FFmpeg render inside a thread-pool worker.

    Each invocation runs in its own thread with its own FFmpeg subprocess.
    The output goes to a shared temp directory (filenames are unique per
    manifest so no collisions).

    After a successful render, the C2PA v2.3 manifest is computed and
    embedded into the MP4 as metadata (fast remux, no re-encode). The
    embedded file replaces the original render output so the stored
    artifact is self-authenticating.
    """
    log.info(
        "render_worker: parallel start candidate=%s platform=%s",
        manifest.candidate_id,
        manifest.platform,
    )
    try:
        result = render_clip(manifest, output_dir=output_dir, timeout_s=300.0)

        # If render succeeded, apply forensic watermark then embed C2PA
        if result.status == "succeeded" and result.output_path:
            try:
                _embed_forensic_watermark(manifest, result)
            except Exception as fw_exc:
                # Forensic watermark is non-critical — log and proceed
                log.warning(
                    "render_worker: forensic watermark skipped for candidate=%s: %s",
                    manifest.candidate_id,
                    fw_exc,
                )

            try:
                _embed_c2pa_manifest(manifest, result)
            except Exception as c2pa_exc:
                # C2PA embedding is non-critical — log and proceed without it
                log.warning(
                    "render_worker: C2PA embedding skipped for candidate=%s: %s",
                    manifest.candidate_id,
                    c2pa_exc,
                )

        return {
            "render_job_id": manifest.render_job_id,
            "candidate_id": manifest.candidate_id,
            "status": result.status,
            "output_path": result.output_path,
            "bytes": result.bytes,
            "duration_s": result.duration_s,
            "elapsed_seconds": result.elapsed_seconds,
            "command": result.command,
            "error": result.error,
        }
    except Exception as exc:
        log.exception(
            "render_worker: parallel crash candidate=%s job=%s",
            manifest.candidate_id,
            job_id_str,
        )
        return {
            "render_job_id": manifest.render_job_id,
            "candidate_id": manifest.candidate_id,
            "status": "failed",
            "output_path": None,
            "bytes": None,
            "duration_s": None,
            "elapsed_seconds": 0.0,
            "command": [],
            "error": str(exc),
        }


def _embed_forensic_watermark(
    manifest: RenderManifest,
    result: RenderExecutionResult,
) -> None:
    """Embed invisible forensic watermark in the rendered clip.

    This is called inside the thread pool worker after a successful
    render, BEFORE C2PA embedding (so the content hash covers the
    watermarked file).

    The watermark encodes the tenant_id, candidate_id, and timestamp
    in a luminance-based pattern that survives re-encoding and moderate
    cropping.

    Failures are non-fatal — the clip is usable without it.
    """
    if not manifest.watermark_forensic:
        return
    output_path = result.output_path
    if not output_path:
        return

    try:
        from api.services.watermarking.forensic import ForensicWatermarker

        import tempfile
        import os

        wm = ForensicWatermarker()
        fd, tmp_path = tempfile.mkstemp(
            suffix=".forensic.mp4",
            prefix="wm_",
            dir=os.path.dirname(output_path),
        )
        os.close(fd)

        embed_result = wm.embed(
            input_path=output_path,
            output_path=tmp_path,
            tenant_id=manifest.tenant_id,
            clip_id=manifest.candidate_id,
        )

        if embed_result.success:
            import shutil

            shutil.move(tmp_path, output_path)
            # Update result with new size
            new_size = os.path.getsize(output_path)
            result.bytes = new_size
            log.info(
                "forensic_wm: embedded in candidate=%s frames=%d",
                manifest.candidate_id,
                embed_result.frames_watermarked,
            )
        else:
            # Cleanup temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            log.warning(
                "forensic_wm: skip candidate=%s reason=%s",
                manifest.candidate_id,
                embed_result.error,
            )
    except ImportError:
        log.debug("forensic_wm: OpenCV not available — skipping")
    except Exception as exc:
        log.warning(
            "forensic_wm: unexpected error for candidate=%s: %s",
            manifest.candidate_id,
            exc,
        )


def _embed_c2pa_manifest(
    manifest: RenderManifest,
    result: RenderExecutionResult,
) -> None:
    """Build + embed C2PA v2.3 manifest into the rendered MP4.

    This is called inside the thread pool worker after a successful
    render. It:
      1. Computes the sha256 content hash of the rendered file
      2. Builds a RenderAssertion with the content hash
      3. Signs the assertion → ProvenanceManifest
      4. Embeds the manifest in the MP4 using FFmpeg remux
      5. Replaces the original file with the C2PA-embedded copy

    Failures are non-fatal (the clip is still usable, just without
    embedded provenance).
    """
    import hashlib
    import os
    import shutil

    from api.services.c2pa import embed_manifest as c2pa_embed

    output_path = result.output_path
    if not output_path:
        return

    # 1. Compute content hash of the rendered file
    sha = hashlib.sha256()
    with open(output_path, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)  # 8 MB
            if not chunk:
                break
            sha.update(chunk)
    content_hash = sha.hexdigest()

    # 2. Build assertion + sign
    try:
        signer = ProvSigner.from_env()
    except RuntimeError:
        log.debug("c2pa_embed: ProvSigner not configured — skipping")
        return

    assertion = assertion_from_manifest(manifest)
    assertion.content_hash = content_hash

    pv_manifest = signer.sign_manifest(assertion, content_hash=content_hash)

    # 3. Embed manifest in MP4
    embed_result = c2pa_embed(
        mp4_path=output_path,
        manifest_json=pv_manifest.model_dump(mode="json"),
        manifest_url=None,  # sidecar URL set by exports router
    )

    if embed_result.success and embed_result.output_path:
        # 4. Replace original with C2PA-embedded copy
        embedded_path = embed_result.output_path
        shutil.move(embedded_path, output_path)

        # Update result with new file size
        new_size = os.path.getsize(output_path)
        result.bytes = new_size
        result.output_path = output_path

        log.info(
            "c2pa_embed: embedded C2PA v2.3 manifest in %s content_hash=%s",
            manifest.candidate_id,
            content_hash[:16],
        )
    else:
        log.warning(
            "c2pa_embed: embedding failed for %s: %s",
            manifest.candidate_id,
            embed_result.error,
        )


def _record_pipeline_timing(
    *,
    job_id: uuid.UUID,
    build_result: ManifestBuildResult,
    render_tasks: list[dict],
    base_results: list[dict],
    completed_results: list[dict],
) -> None:
    """Record per-stage pipeline timing on the Job row.

    This runs in its own DB session so it doesn't interfere with the
    render persistence session. Failures are logged but not propagated
    (timing is informational, not critical).
    """
    try:
        all_results = base_results + completed_results
        elapsed_times = [
            t.get("elapsed_seconds", 0.0)
            for t in all_results
            if t.get("elapsed_seconds") is not None
        ]
        now_iso = datetime.now(timezone.utc).isoformat()

        timing = {
            "render_batch_started": now_iso,
            "render_batch_completed": now_iso,
            "render_count": len(build_result.manifests),
            "render_parallel_count": len(render_tasks),
            "render_total_elapsed_s": sum(elapsed_times) if elapsed_times else 0.0,
            "render_max_elapsed_s": max(elapsed_times) if elapsed_times else 0.0,
            "render_avg_elapsed_s": (
                sum(elapsed_times) / len(elapsed_times) if elapsed_times else 0.0
            ),
        }

        with SessionLocal() as db:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
            if job is not None:
                existing = job.pipeline_timing or {}
                existing.update(timing)
                job.pipeline_timing = existing
                db.commit()
                log.info(
                    "pipeline_timing: job=%s timing=%s",
                    job_id,
                    timing,
                )
    except Exception:
        log.exception("pipeline_timing: failed to record timing for job=%s", job_id)
