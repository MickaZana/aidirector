"""Cloudflare R2 access — S3-compatible API, plus deterministic local-mode fallback.

Two modes:
  - **R2 mode** (production): full R2 credentials present in settings. Uses
    boto3 to presign uploads/downloads and to upload local files.
  - **Local mode** (dev/probes): credentials absent. Falls back to a local
    storage mirror at `<repo>/apps/api/_local_storage/`. All path-shape
    helpers behave identically; only the underlying transport differs.

Storage URI scheme:
  r2://{bucket}/{key}      — R2 mode
  local://{absolute_path}  — local-mode fallback

Key conventions (plan §7):
  tenant/{tenant_id}/upload/{upload_id}/...
  tenant/{tenant_id}/render/{render_id}/...
  tenant/{tenant_id}/exports/{export_id}/{filename}
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from api.config import get_settings

# Deterministic local mirror — predictable, tenant-scoped, safe for probes.
_LOCAL_MIRROR_DEFAULT = Path(__file__).resolve().parents[4] / "_local_storage"


def is_r2_configured() -> bool:
    s = get_settings()
    return bool(s.r2_account_id and s.r2_access_key_id and s.r2_secret_access_key and s.r2_bucket)


def local_mirror_path() -> Path:
    """Where local-mode files live. Override via env var for tests."""
    import os

    override = os.environ.get("LOCAL_STORAGE_MIRROR")
    if override:
        return Path(override)
    return _LOCAL_MIRROR_DEFAULT


# --- Key builders (always deterministic, scheme-agnostic) ------------------


def upload_key(tenant_id: str, upload_id: str, filename: str) -> str:
    return f"tenant/{tenant_id}/upload/{upload_id}/{filename}"


def render_key(tenant_id: str, render_id: str, filename: str) -> str:
    return f"tenant/{tenant_id}/render/{render_id}/{filename}"


def export_key(tenant_id: str, export_id: str, filename: str) -> str:
    return f"tenant/{tenant_id}/exports/{export_id}/{filename}"


# --- URI builders (scheme-aware) -------------------------------------------


def build_storage_uri(key: str) -> str:
    """Return a storage URI for a key under the active transport mode."""
    if is_r2_configured():
        s = get_settings()
        return f"r2://{s.r2_bucket}/{key}"
    abs_path = local_mirror_path() / key
    return f"local://{abs_path.as_posix()}"


def parse_storage_uri(uri: str) -> tuple[str, str]:
    """('r2'|'local', key_or_path)."""
    if uri.startswith("r2://"):
        rest = uri[len("r2://") :]
        bucket, _, key = rest.partition("/")
        return "r2", key
    if uri.startswith("local://"):
        return "local", uri[len("local://") :]
    raise ValueError(f"Unsupported storage URI: {uri!r}")


# --- Transport (mode-dispatched) -------------------------------------------


def put_local_file(local_path: Path, key: str) -> str:
    """Upload a local file to storage; return the storage URI it landed at.

    In R2 mode: boto3 put_object.
    In local mode: copy to the mirror at `<mirror>/{key}`.
    """
    if is_r2_configured():
        client = _client()
        s = get_settings()
        with local_path.open("rb") as f:
            client.put_object(Bucket=s.r2_bucket, Key=key, Body=f)
        return f"r2://{s.r2_bucket}/{key}"

    dst = local_mirror_path() / key
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_path, dst)
    return f"local://{dst.as_posix()}"


def presign_put(key: str, content_type: str, expires_s: int = 3600) -> str:
    """Return a presigned PUT URL the client can upload to directly."""
    if not is_r2_configured():
        # Stub — local mode does not presign.
        return f"local-presign-stub://{key}"
    s = get_settings()
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": s.r2_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_s,
    )


def presign_get(key: str, expires_s: int = 3600) -> str:
    """Return a presigned GET URL for downloads."""
    if not is_r2_configured():
        abs_path = local_mirror_path() / key
        return f"local://{abs_path.as_posix()}"
    s = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.r2_bucket, "Key": key},
        ExpiresIn=expires_s,
    )


def _client() -> Any:
    """Lazy R2 client. Never called in local mode."""
    import boto3
    from botocore.client import Config

    s = get_settings()
    endpoint = f"https://{s.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4", region_name="auto"),
    )
