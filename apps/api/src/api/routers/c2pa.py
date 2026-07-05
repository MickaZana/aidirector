"""C2PA v2.3 compliance router — trust anchor + DID resolution + forensic watermark detection.

Provides endpoints that consumers (broadcasters, rights-holders, automated
verifiers) use to verify Content Credentials on AI Director clips.

Endpoints:
  - GET  /api/v1/c2pa/trust-anchor          — Self-hosted trust anchor registry
  - GET  /api/v1/c2pa/registry              — Same, alias for discoverability
  - POST /api/v1/c2pa/forensic-detect       — Detect forensic watermark in a clip

The trust anchor lists all active signing keys with their DIDs, first-seen
timestamps, and trust levels. Consumers fetch this to verify that a signing
key was registered by a known AI Director instance.

For full C2PA v2.3 verification, consumers should:
  1. Extract the c2pa_manifest metadata tag from the MP4
  2. Verify the Ed25519 signature using the public key from the DID document
  3. Check the key_id is in the trust anchor registry (this endpoint)
  4. Verify the content_hash matches the file bytes

For forensic watermark detection:
  1. Upload a clip or provide an R2 URI
  2. The detector extracts the luminance-based watermark pattern
  3. Returns presence, confidence, and decoded payload fields
"""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import TenantRow
from api.services.c2pa import get_trust_anchor

log = logging.getLogger(__name__)

router = APIRouter(prefix="/c2pa", tags=["c2pa"])


class TrustAnchorOut(BaseModel):
    """Response shape for the trust anchor endpoint."""

    anchor: dict
    keys: dict


class ForensicDetectOut(BaseModel):
    """Response shape for forensic watermark detection."""

    present: bool
    confidence: float = 0.0
    payload: str | None = None
    decoded_fields: dict | None = None
    frames_analyzed: int = 0
    error: str | None = None


# ── Trust anchor ────────────────────────────────────────────────────────────


@router.get("/trust-anchor", response_model=TrustAnchorOut)
def get_trust_anchor_endpoint() -> TrustAnchorOut:
    """Return the C2PA trust anchor registry.

    Contains all signing keys registered by this AI Director instance,
    their DIDs, first-seen timestamps, and trust levels.
    """
    ta = get_trust_anchor()
    registry = ta.get_registry_json()
    return TrustAnchorOut(anchor=registry["anchor"], keys=registry["keys"])


@router.get("/registry", response_model=TrustAnchorOut)
def get_trust_anchor_registry() -> TrustAnchorOut:
    """Alias for GET /trust-anchor — improves discoverability."""
    return get_trust_anchor_endpoint()


# ── Retention policy ────────────────────────────────────────────────────────


class RetentionConfigOut(BaseModel):
    """Current retention policy configuration."""

    retention_days: int
    env_var: str = "RETENTION_DAYS"


class RetentionApplyOut(BaseModel):
    """Result of an ad-hoc retention policy run."""

    jobs_expired: int
    r2_keys_deleted: int
    errors: list[str] | None = None
    dry_run: bool = False


@router.get("/retention", response_model=RetentionConfigOut)
def get_retention_config() -> RetentionConfigOut:
    """Return the current retention policy configuration."""
    from api.services.retention import retention_days_setting

    return RetentionConfigOut(retention_days=retention_days_setting())


@router.post("/retention/apply", response_model=RetentionApplyOut)
def apply_retention(
    dry_run: bool = True,
    retention_days: int | None = None,
) -> RetentionApplyOut:
    """Apply the retention policy immediately.

    By default runs in dry_run mode — set `dry_run=false` to perform
    actual deletions. Use `retention_days` to override the configured
    retention period for this run.

    In production this runs automatically via Modal cron every 24h.
    This endpoint exists for ad-hoc execution and testing.
    """
    from api.services.retention import apply_retention_policy

    result = apply_retention_policy(retention_days=retention_days, dry_run=dry_run)
    return RetentionApplyOut(
        jobs_expired=result.jobs_expired,
        r2_keys_deleted=result.r2_keys_deleted,
        errors=result.errors,
        dry_run=result.dry_run,
    )


# ── Forensic watermark detection ────────────────────────────────────────────


@router.post("/forensic-detect", response_model=ForensicDetectOut)
async def detect_forensic_watermark(
    file: UploadFile,
    tenant: TenantRow,
) -> ForensicDetectOut:
    """Detect an invisible forensic watermark in an uploaded clip.

    Upload a clip (MP4) to check if it contains an AI Director forensic
    watermark. The detector analyzes the luminance channel across frames
    and cross-correlates against expected watermark patterns.

    Returns:
      - present: whether a forensic watermark was detected
      - confidence: correlation strength (0.0-1.0 scale)
      - payload: detected payload hash (if watermarked)
      - decoded_fields: human-readable detection metadata
      - frames_analyzed: number of frames processed
    """
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Only MP4 files are supported for forensic detection",
        )

    # Save the uploaded file to a temp location
    try:
        suffix = Path(file.filename).suffix or ".mp4"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="forensic_detect_")
        import os

        os.close(fd)

        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Failed to save uploaded file: {exc}",
        )

    # Run detection
    try:
        from api.services.watermarking.forensic import ForensicWatermarker

        wm = ForensicWatermarker()
        result = wm.detect(tmp_path)
    except Exception as exc:
        log.exception("forensic_detect: detection failed")
        result = ForensicDetectOut(present=False, error=f"Detection error: {exc}")
    finally:
        # Cleanup
        try:
            import os as _os

            _os.unlink(tmp_path)
        except OSError:
            pass

    return ForensicDetectOut(
        present=result.present,
        confidence=result.confidence,
        payload=result.payload,
        decoded_fields=result.decoded_fields,
        frames_analyzed=result.frames_analyzed,
        error=result.error,
    )
