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
    """Phase 5.5: read RenderJob from Postgres, hydrate manifest, render,
    persist. Stub until the DB-driven loader path is wired."""
    raise NotImplementedError(
        "Phase 5.5 — read RenderJob.settings manifest from DB, run adapter, persist."
    )
