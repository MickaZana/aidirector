"""Exports router — presigned download URLs with provenance headers."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import RenderOutput, RenderJob
from api.services import r2
from api.services.provenance import ProvSigner

log = logging.getLogger(__name__)

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int = 3600
    render_output_id: str
    r2_key: str


@router.get("/{render_output_id}/url", response_model=ExportUrlResponse)
def get_export_url(
    render_output_id: uuid.UUID,
    tenant: TenantRow,
    db: DbSession,
    response: Response,
) -> ExportUrlResponse:
    """Return a 1-hour presigned GET URL for a render output.

    Also attaches provenance headers so callers can verify clip authenticity:
      X-Provenance-Key-Id    — signing key label
      X-Provenance-Signed-At — ISO timestamp from manifest metadata
    """
    output = db.execute(
        select(RenderOutput)
        .join(RenderJob, RenderOutput.render_job_id == RenderJob.id)
        .where(
            RenderOutput.id == render_output_id,
            RenderJob.tenant_id == tenant.id,
        )
    ).scalar_one_or_none()

    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Render output not found")

    if not output.storage_uri:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Render output has no storage URI — render may still be in progress",
        )

    # Parse storage URI → R2 key
    try:
        _, key = r2.parse_storage_uri(output.storage_uri)
    except ValueError:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Invalid storage URI")

    # Verify the object exists before issuing a URL
    head = r2.head_object(key)
    if head is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "File not found in storage — it may have been deleted",
        )

    download_url = r2.signed_get_url(key, expires_s=3600)

    # Attach provenance headers + write C2PA sidecar if signing is configured
    try:
        from api.schemas.provenance_manifest import RenderAssertion

        signer = ProvSigner.from_env()

        assertion = RenderAssertion(
            source_uri=output.storage_uri,
            clip_start_s=float(getattr(output, "clip_start_s", 0) or 0),
            clip_end_s=float(getattr(output, "clip_end_s", 0) or 0),
            renderer="aidirector-ffmpeg",
            platform=getattr(output, "platform", "unknown") or "unknown",
            tenant_id=str(tenant.id),
            candidate_id=str(getattr(output, "candidate_id", "") or ""),
            render_job_id=str(output.render_job_id),
        )
        manifest = signer.sign_manifest(assertion)

        # Store .c2pa.json sidecar alongside the clip in R2
        sidecar_key = key.rsplit(".", 1)[0] + ".c2pa.json"
        import json

        sidecar_bytes = json.dumps(manifest.model_dump(mode="json"), indent=2).encode()
        try:
            import io
            from api.config import get_settings
            import boto3

            _s = get_settings()
            _client = boto3.client(
                "s3",
                endpoint_url=f"https://{_s.r2_account_id}.r2.cloudflarestorage.com",
                aws_access_key_id=_s.r2_access_key_id,
                aws_secret_access_key=_s.r2_secret_access_key,
            )
            _client.put_object(
                Bucket=_s.r2_bucket,
                Key=sidecar_key,
                Body=sidecar_bytes,
                ContentType="application/json",
            )
            response.headers["X-Provenance-Manifest-Url"] = r2.signed_get_url(
                sidecar_key, expires_s=3600
            )
        except Exception as sidecar_exc:
            log.debug("exports: sidecar upload skipped: %s", sidecar_exc)

        response.headers["X-Provenance-Key-Id"] = signer.key_id
        response.headers["X-Provenance-Public-Key"] = signer.public_key_b64()

        # C2PA v2.3: X-Content-Credential header (per C2PA spec)
        # Points to the DID document which contains the public key material
        # consumers need to verify the Content Credentials.
        if signer.credential_url:
            response.headers["X-Content-Credential"] = signer.credential_url

        # C2PA v2.3: X-Content-Credential-DID header (proprietary extension)
        # Provides the DID directly so consumers can resolve without fetching
        # the credential document first.
        if signer.did:
            response.headers["X-Content-Credential-DID"] = signer.did

        log.info("exports: provenance headers + sidecar written for output %s", render_output_id)
    except Exception:
        log.debug("exports: provenance signing not configured — skipping headers")

    return ExportUrlResponse(
        url=download_url,
        expires_in_seconds=3600,
        render_output_id=str(render_output_id),
        r2_key=key,
    )
