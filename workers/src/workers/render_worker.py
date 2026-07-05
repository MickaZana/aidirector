"""Render worker — Modal-side wrapper over the render plan adapter.

The worker contains NO encoding logic, NO FFmpeg argument building, and
NO DirectorPlan reading. It receives a serialised `RenderManifest`, hands
it to the adapter, and persists the result via the persistence service.

The boundary is intentional: a future renderer swap (HyperFrames on Modal
GPU, Remotion via Node) replaces the adapter only — the worker, the
manifest, and the persistence layer all stay unchanged.

Entrypoints:
  - `render_one_fixture(manifest_dict, output_dir)` — phase 5 fixture path
  - `render_one(render_job_id, tenant_slug)` — phase 5.5 stub (reads
    manifest from DB)
"""

from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=4096)
def render_one_fixture(manifest_dict: dict, output_dir: str) -> dict:
    """Phase 5 path: caller supplies a manifest dict; we render to local disk
    inside the Modal container and return the execution result."""
    from pathlib import Path

    from api.schemas.render_manifest import RenderManifest
    from api.services.intel.render_plan_adapter import render_clip

    manifest = RenderManifest.model_validate(manifest_dict)
    result = render_clip(manifest, output_dir=Path(output_dir))
    return result.model_dump(mode="json")


@app.function(image=intel_image, secrets=secrets, timeout=1800, memory=8192)
def render_one(render_job_id: str, tenant_slug: str) -> dict:
    """Read RenderJob from Postgres, hydrate manifest, render, persist.

    Expects the RenderJob.settings to contain a 'manifest' key with a
    serialised RenderManifest dict (stored by the dispatcher when the
    render job was enqueued).
    """
    import uuid
    import sys
    from pathlib import Path

    # Add api package to path (Modal mounts it at /api_src)
    api_src = Path("/api_src")
    if api_src.exists() and str(api_src) not in sys.path:
        sys.path.insert(0, str(api_src))

    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from api.db import engine
    from api.models import Job, RenderJob as RenderJobModel, RenderJobStatus
    from api.schemas.render_manifest import RenderManifest
    from api.services.intel.render_plan_adapter import render_clip
    from api.services.render_output_persistence import (
        start_render_job,
        complete_render_job,
        fail_render_job,
    )

    assert engine is not None, "DATABASE_URL must be set"

    with Session(engine) as db:
        rj = db.execute(
            select(RenderJobModel).where(RenderJobModel.id == uuid.UUID(render_job_id))
        ).scalar_one_or_none()
        if rj is None:
            raise ValueError(f"RenderJob {render_job_id} not found")

        job = db.execute(select(Job).where(Job.id == rj.job_id)).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {rj.job_id} not found for RenderJob {render_job_id}")

        settings = rj.settings or {}
        manifest_dict = settings.get("manifest")
        if not manifest_dict:
            raise ValueError(f"RenderJob {render_job_id} has no manifest in settings")

        manifest = RenderManifest.model_validate(manifest_dict)

        import tempfile

        output_dir = Path(tempfile.mkdtemp(prefix="aidirector_render_"))
        result = render_clip(manifest, output_dir=output_dir, timeout_s=300.0)

        if result.status == "succeeded":
            r2_key = f"local://{result.output_path}"
            complete_render_job(
                db, job=job, render_job=rj, manifest=manifest, result=result, r2_key=r2_key
            )
        else:
            fail_render_job(db, job=job, render_job=rj, manifest=manifest, result=result)

        db.commit()
        return result.model_dump(mode="json")
