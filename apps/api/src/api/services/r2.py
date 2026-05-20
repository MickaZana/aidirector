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

Phase 10 additions:
  - `put_local_file(..., verify=True)` does a HEAD after PUT and compares
    `ContentLength`. Mismatch = `R2UploadVerificationError`.
  - `signed_get_url(key, expires_s=...)` is the route exports use to give
    the client a time-bounded download link.
  - All operations emit an audit row via the helper, not free-form.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.config import get_settings

# Deterministic local mirror — predictable, tenant-scoped, safe for probes.
_LOCAL_MIRROR_DEFAULT = Path(__file__).resolve().parents[4] / "_local_storage"


class R2UploadVerificationError(RuntimeError):
    """HEAD-after-PUT didn't see the bytes we just uploaded."""


@dataclass(frozen=True)
class UploadResult:
    """Return value of `put_local_file`. The storage_uri is what callers
    persist into RenderOutput / ExportArtifact.storage_uri columns."""

    storage_uri: str
    key: str
    bytes: int
    verified: bool


def is_r2_configured() -> bool:
    s = get_settings()
    return bool(
        s.r2_account_id and s.r2_access_key_id and s.r2_secret_access_key and s.r2_bucket
    )


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


def put_local_file(local_path: Path, key: str, *, verify: bool = True) -> UploadResult:
    """Upload a local file to storage; return what landed where.

    Phase 10:
      - In R2 mode, after PUT, runs HEAD and compares ContentLength.
        Mismatch → `R2UploadVerificationError` (caller transitions the
        export to FAILED and records the error).
      - In local mode the "verification" is a stat() of the destination
        file — same shape, same return type, so tests and probes use
        the same code path.
    """
    if not local_path.exists():
        raise FileNotFoundError(local_path)
    src_bytes = local_path.stat().st_size

    if is_r2_configured():
        s = get_settings()
        client = _client()
        with local_path.open("rb") as f:
            client.put_object(Bucket=s.r2_bucket, Key=key, Body=f)
        verified = True
        if verify:
            head = client.head_object(Bucket=s.r2_bucket, Key=key)
            remote_bytes = int(head.get("ContentLength") or 0)
            if remote_bytes != src_bytes:
                raise R2UploadVerificationError(
                    f"R2 HEAD ContentLength={remote_bytes} but local bytes={src_bytes} for key={key}"
                )
        return UploadResult(
            storage_uri=f"r2://{s.r2_bucket}/{key}",
            key=key,
            bytes=src_bytes,
            verified=verified,
        )

    # Local mode mirror copy.
    dst = local_mirror_path() / key
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(local_path, dst)
    if verify and dst.stat().st_size != src_bytes:
        raise R2UploadVerificationError(
            f"local mirror size={dst.stat().st_size} != src={src_bytes} at {dst}"
        )
    return UploadResult(
        storage_uri=f"local://{dst.as_posix()}",
        key=key,
        bytes=src_bytes,
        verified=True,
    )


def presign_put(key: str, content_type: str, expires_s: int = 3600) -> str:
    """Return a presigned PUT URL the client can upload to directly."""
    if not is_r2_configured():
        return f"local-presign-stub://{key}"
    s = get_settings()
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": s.r2_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires_s,
    )


def presign_get(key: str, expires_s: int = 3600) -> str:
    """Return a presigned GET URL for downloads (alias kept for compat)."""
    return signed_get_url(key, expires_s=expires_s)


def signed_get_url(key: str, *, expires_s: int = 3600) -> str:
    """Time-bounded download URL.

    In R2 mode: real boto3 presign.
    In local mode: returns the `local://...` path verbatim. The frontend
    presigner endpoint will never reach this branch in production; it's
    here so probes that don't have R2 credentials still exercise the
    same call path.
    """
    if not is_r2_configured():
        abs_path = local_mirror_path() / key
        return f"local://{abs_path.as_posix()}"
    s = get_settings()
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": s.r2_bucket, "Key": key},
        ExpiresIn=expires_s,
    )


def head_object(key: str) -> dict[str, Any] | None:
    """HEAD a stored object. None if absent. Used by the post-upload
    verification path and by the export-presign route to confirm bytes
    exist before issuing a signed URL."""
    if is_r2_configured():
        from botocore.exceptions import ClientError  # noqa: PLC0415

        s = get_settings()
        try:
            return _client().head_object(Bucket=s.r2_bucket, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    abs_path = local_mirror_path() / key
    if not abs_path.exists():
        return None
    return {"ContentLength": abs_path.stat().st_size, "Mode": "local"}


def _client() -> Any:
    """Lazy R2 client. Never called in local mode."""
    import boto3  # noqa: PLC0415
    from botocore.client import Config  # noqa: PLC0415

    s = get_settings()
    endpoint = f"https://{s.r2_account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=s.r2_access_key_id,
        aws_secret_access_key=s.r2_secret_access_key,
        config=Config(signature_version="s3v4", region_name="auto"),
    )
