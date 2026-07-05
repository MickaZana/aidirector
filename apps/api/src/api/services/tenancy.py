"""Tenant resolution.

Clerk `org_id` (or `user_<id>` for personal tenants) is the durable external
identity. We store it in `Tenant.slug` for now — when org_id semantics need to
diverge from a user-facing slug, add a dedicated column and migrate.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.auth import ClerkClaims
from api.models import Tenant


def get_or_create_tenant(db: Session, claims: ClerkClaims) -> Tenant:
    """Look up by Clerk org_id (stored in `tenants.slug`); create if missing."""
    return get_or_create_tenant_by_ids(db, org_id=claims.tenant_id, org_name=claims.tenant_id)


def get_or_create_tenant_by_ids(db: Session, org_id: str, org_name: str = "") -> Tenant:
    """Upsert tenant by external org_id — used by webhook handlers."""
    tenant = db.execute(select(Tenant).where(Tenant.slug == org_id)).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(slug=org_id, name=org_name or org_id, plan="starter")
        db.add(tenant)
        db.flush()
    elif org_name and tenant.name != org_name:
        tenant.name = org_name
    return tenant
