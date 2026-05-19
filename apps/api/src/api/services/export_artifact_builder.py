"""ExportArtifactBuilder — canonical export identity.

A pure-function builder that turns a `RenderOutput` row into the inputs
required to write an `ExportArtifact` row. Does NOT write to the DB itself
— that's `export_persistence`. This separation keeps:
  - identity computation testable in isolation
  - DB session ownership clearly in the persistence layer
  - downstream callers (worker, probe, API route) using one shared
    deterministic identity function

Determinism rules:
  - Same (render_output_id, platform, export_version) → same export_hash
  - Same file bytes → same content_hash
  - Same (tenant_slug, candidate_id, platform, export_version, container)
    → same filename
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from api.models import RenderOutput
from api.services.r2 import build_storage_uri, export_key


# Read in chunks so multi-gigabyte renders don't OOM us.
_HASH_CHUNK_BYTES = 1 * 1024 * 1024


@dataclass(frozen=True)
class ExportArtifactInputs:
    """All the fields needed to write an ExportArtifact row.

    Frozen + hashable → safe to pass between worker → API → persistence
    without leakage. The persistence layer is the only place that adds the
    UUID PK and timestamps.
    """

    export_id: uuid.UUID
    render_output_id: uuid.UUID
    tenant_id: uuid.UUID
    platform: str
    export_version: int
    export_hash: str
    content_hash: str
    content_bytes: int
    filename: str
    storage_uri: str
    artifact_metadata: dict


def build_export_artifact(
    *,
    render_output: RenderOutput,
    tenant_slug: str,
    candidate_id: uuid.UUID,
    platform: str,
    local_source_path: Path,
    export_version: int = 1,
    container: str = "mp4",
    extra_metadata: dict | None = None,
) -> ExportArtifactInputs:
    """Build canonical export identity from a freshly-rendered file.

    `local_source_path` is the file the renderer just produced; we hash it
    in place (small chunks) and synthesise the storage URI for the
    eventual upload. The actual transport happens elsewhere (the worker
    calls `r2.put_local_file` before this row gets marked UPLOADED).
    """
    if not local_source_path.exists():
        raise FileNotFoundError(f"render output not on disk: {local_source_path}")

    export_id = uuid.uuid4()
    content_hash = _sha256_file(local_source_path)
    content_bytes = local_source_path.stat().st_size

    # Deterministic identity hash. Stable across re-runs of the builder for
    # the same logical export — useful for idempotent INSERTs.
    export_hash = hashlib.sha256(
        f"{render_output.id}|{platform}|{export_version}".encode("utf-8")
    ).hexdigest()

    filename = _deterministic_filename(
        tenant_slug=tenant_slug,
        candidate_id=candidate_id,
        platform=platform,
        export_version=export_version,
        container=container,
    )

    storage_uri = build_storage_uri(
        export_key(str(render_output.tenant_id), str(export_id), filename)
    )

    metadata: dict = {
        "render_output_id": str(render_output.id),
        "render_job_id": str(render_output.render_job_id),
        "candidate_id": str(candidate_id),
        "aspect_ratio": render_output.aspect_ratio,
        "duration_s": render_output.duration_s,
        "render_bytes": render_output.bytes,
        "platform": platform,
        "export_version": export_version,
        "container": container,
        "source_local_path": str(local_source_path),
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    return ExportArtifactInputs(
        export_id=export_id,
        render_output_id=render_output.id,
        tenant_id=render_output.tenant_id,
        platform=platform,
        export_version=export_version,
        export_hash=export_hash,
        content_hash=content_hash,
        content_bytes=content_bytes,
        filename=filename,
        storage_uri=storage_uri,
        artifact_metadata=metadata,
    )


# --- Internals -------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(_HASH_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _deterministic_filename(
    *,
    tenant_slug: str,
    candidate_id: uuid.UUID,
    platform: str,
    export_version: int,
    container: str,
) -> str:
    """Same inputs → same name forever. Slug→platform→short-candidate→version.

    Underscores only. No timestamps in the name (timestamps lock identity
    to wall-clock; we want lineage-driven identity).
    """
    short_cand = str(candidate_id).split("-")[0]
    return f"{tenant_slug}_{platform}_{short_cand}_v{export_version}.{container}"
