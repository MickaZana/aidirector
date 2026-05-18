"""Uploads router — first half of the MVP loop.

POST /api/uploads creates an Upload row and returns the presign payload.
Clients PUT the file to R2 directly using the returned URL, then POST
/api/uploads/{id}/complete to mark it ready.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import Claims, DbSession, TenantRow
from api.models import Upload, UploadStatus, User, UsageEventType
from api.services.usage_events import emit_usage_event

router = APIRouter(prefix="/uploads", tags=["uploads"])


class PresignRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"
    size_bytes: int
    sport: str = "football"


class PresignResponse(BaseModel):
    upload_id: str
    r2_key: str
    url: str
    fields: dict[str, str]


class UploadView(BaseModel):
    id: str
    tenant_id: str
    filename: str
    r2_key: str
    bytes: int | None
    duration_s: float | None
    sport: str
    status: str
    created_at: str


@router.post("/presign", response_model=PresignResponse, status_code=status.HTTP_201_CREATED)
def presign(
    req: PresignRequest,
    tenant: TenantRow,
    claims: Claims,
    db: DbSession,
) -> PresignResponse:
    """Create Upload row + return presigned R2 URL.

    Phase 0: persist the row; presign URL is a stub returning the contract shape.
    The real R2 presigner lives in api.services.r2 — wired in phase 1.
    """
    upload_id = uuid.uuid4()
    r2_key = f"tenant/{tenant.id}/upload/{upload_id}/{req.filename}"

    user = db.execute(
        select(User).where(User.clerk_user_id == claims.user_id)
    ).scalar_one_or_none()

    upload = Upload(
        id=upload_id,
        tenant_id=tenant.id,
        user_id=user.id if user else None,
        r2_key=r2_key,
        filename=req.filename,
        bytes=req.size_bytes,
        sport=req.sport,
        status=UploadStatus.PENDING.value,
        upload_metadata={"content_type": req.content_type},
    )
    db.add(upload)

    emit_usage_event(
        db,
        tenant_id=tenant.id,
        upload_id=upload_id,
        event_type=UsageEventType.UPLOAD_CREATED,
        unit="upload",
        metadata={"filename": req.filename, "size_bytes": req.size_bytes},
    )
    db.commit()

    return PresignResponse(
        upload_id=str(upload_id),
        r2_key=r2_key,
        url="https://stub.r2.cloudflarestorage.com/aidirector",
        fields={"stub": "phase_0_not_yet_wired"},
    )


@router.post("/{upload_id}/complete", response_model=UploadView)
def mark_complete(
    upload_id: uuid.UUID,
    tenant: TenantRow,
    db: DbSession,
) -> UploadView:
    """Client calls this after PUT to R2 succeeds."""
    upload = db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")

    upload.status = UploadStatus.READY.value
    db.commit()
    return _serialize(upload)


@router.get("", response_model=list[UploadView])
def list_uploads(tenant: TenantRow, db: DbSession) -> list[UploadView]:
    rows = (
        db.execute(
            select(Upload).where(Upload.tenant_id == tenant.id).order_by(Upload.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_serialize(u) for u in rows]


@router.get("/{upload_id}", response_model=UploadView)
def get_upload(upload_id: uuid.UUID, tenant: TenantRow, db: DbSession) -> UploadView:
    upload = db.execute(
        select(Upload).where(Upload.id == upload_id, Upload.tenant_id == tenant.id)
    ).scalar_one_or_none()
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return _serialize(upload)


def _serialize(upload: Upload) -> UploadView:
    return UploadView(
        id=str(upload.id),
        tenant_id=str(upload.tenant_id),
        filename=upload.filename,
        r2_key=upload.r2_key,
        bytes=upload.bytes,
        duration_s=upload.duration_s,
        sport=upload.sport,
        status=upload.status,
        created_at=upload.created_at.isoformat(),
    )
