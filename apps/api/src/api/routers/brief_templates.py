"""Brief Templates router — CRUD + marketplace for reusable DirectorPlan brief presets.

POST   /api/brief-templates                    create
GET    /api/brief-templates                    list (filter: sport=, tag=)
GET    /api/brief-templates/marketplace        public templates from all tenants
GET    /api/brief-templates/{id}               get one
PATCH  /api/brief-templates/{id}               partial update
DELETE /api/brief-templates/{id}               delete
POST   /api/brief-templates/{id}/fork          fork a public template to caller's tenant
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from api.deps import DbSession, TenantRow
from api.models import BriefTemplate

router = APIRouter(prefix="/brief-templates", tags=["brief-templates"])


# --- I/O schemas ------------------------------------------------------------

class BriefTemplateCreate(BaseModel):
    name: str
    description: str | None = None
    sport: str | None = None
    render_style: str | None = None
    caption_style: str | None = None
    pacing: str | None = None
    hook_phrases: list[str] = []
    tags: list[str] = []
    is_public: bool = False


class BriefTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sport: str | None = None
    render_style: str | None = None
    caption_style: str | None = None
    pacing: str | None = None
    hook_phrases: list[str] | None = None
    tags: list[str] | None = None
    is_public: bool | None = None


class BriefTemplateOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    sport: str | None
    render_style: str | None
    caption_style: str | None
    pacing: str | None
    hook_phrases: list[str]
    tags: list[str]
    is_public: bool
    use_count: int
    created_at: str
    updated_at: str


# --- Endpoints --------------------------------------------------------------

@router.get("/marketplace", response_model=list[BriefTemplateOut])
def list_marketplace(
    db: DbSession,
    _tenant: TenantRow,
    sport: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> list[BriefTemplateOut]:
    """List public templates from all tenants, ordered by use_count desc."""
    q = (
        select(BriefTemplate)
        .where(BriefTemplate.is_public.is_(True))
        .order_by(BriefTemplate.use_count.desc(), BriefTemplate.created_at.desc())
        .limit(limit)
    )
    if sport:
        q = q.where(BriefTemplate.sport == sport)
    rows = db.execute(q).scalars().all()
    return [_serialize(r) for r in rows]


@router.post("/{template_id}/fork", response_model=BriefTemplateOut, status_code=status.HTTP_201_CREATED)
def fork_template(
    template_id: uuid.UUID, tenant: TenantRow, db: DbSession
) -> BriefTemplateOut:
    """Fork a public template into the caller's tenant and increment use_count."""
    source = db.execute(
        select(BriefTemplate).where(
            BriefTemplate.id == template_id,
            BriefTemplate.is_public.is_(True),
        )
    ).scalar_one_or_none()
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found or not public")

    fork = BriefTemplate(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=f"{source.name} (fork)",
        description=source.description,
        sport=source.sport,
        render_style=source.render_style,
        caption_style=source.caption_style,
        pacing=source.pacing,
        hook_phrases=list(source.hook_phrases or []),
        tags=list(source.tags or []),
        is_public=False,
        use_count=0,
    )
    db.add(fork)
    source.use_count = (source.use_count or 0) + 1
    db.commit()
    db.refresh(fork)
    return _serialize(fork)


@router.post("", response_model=BriefTemplateOut, status_code=status.HTTP_201_CREATED)
def create_brief_template(
    body: BriefTemplateCreate, tenant: TenantRow, db: DbSession
) -> BriefTemplateOut:
    row = BriefTemplate(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=body.name,
        description=body.description,
        sport=body.sport,
        render_style=body.render_style,
        caption_style=body.caption_style,
        pacing=body.pacing,
        hook_phrases=body.hook_phrases,
        tags=body.tags,
        is_public=body.is_public,
        use_count=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("", response_model=list[BriefTemplateOut])
def list_brief_templates(
    tenant: TenantRow,
    db: DbSession,
    sport: str | None = Query(default=None),
    tag: str | None = Query(default=None, description="Filter by tag (substring match)"),
) -> list[BriefTemplateOut]:
    q = select(BriefTemplate).where(BriefTemplate.tenant_id == tenant.id)
    if sport:
        q = q.where(BriefTemplate.sport == sport)
    rows = db.execute(q.order_by(BriefTemplate.created_at.desc())).scalars().all()
    if tag:
        rows = [r for r in rows if any(tag.lower() in t.lower() for t in (r.tags or []))]
    return [_serialize(r) for r in rows]


@router.get("/{template_id}", response_model=BriefTemplateOut)
def get_brief_template(
    template_id: uuid.UUID, tenant: TenantRow, db: DbSession
) -> BriefTemplateOut:
    row = _get_or_404(db, template_id, tenant.id)
    return _serialize(row)


@router.patch("/{template_id}", response_model=BriefTemplateOut)
def update_brief_template(
    template_id: uuid.UUID,
    body: BriefTemplateUpdate,
    tenant: TenantRow,
    db: DbSession,
) -> BriefTemplateOut:
    row = _get_or_404(db, template_id, tenant.id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brief_template(
    template_id: uuid.UUID, tenant: TenantRow, db: DbSession
) -> None:
    row = _get_or_404(db, template_id, tenant.id)
    db.delete(row)
    db.commit()


# --- Helpers ----------------------------------------------------------------

def _get_or_404(db: DbSession, template_id: uuid.UUID, tenant_id: uuid.UUID) -> BriefTemplate:
    row = db.execute(
        select(BriefTemplate).where(
            BriefTemplate.id == template_id,
            BriefTemplate.tenant_id == tenant_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brief template not found")
    return row


def _serialize(row: BriefTemplate) -> BriefTemplateOut:
    return BriefTemplateOut(
        id=str(row.id),
        tenant_id=str(row.tenant_id),
        name=row.name,
        description=row.description,
        sport=row.sport,
        render_style=row.render_style,
        caption_style=row.caption_style,
        pacing=row.pacing,
        hook_phrases=row.hook_phrases or [],
        tags=row.tags or [],
        is_public=bool(row.is_public),
        use_count=int(row.use_count or 0),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )
