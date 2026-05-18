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
    stmt = select(Tenant).where(Tenant.slug == claims.tenant_id)
    tenant = db.execute(stmt).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(slug=claims.tenant_id, name=claims.tenant_id, plan="creator")
        db.add(tenant)
        db.flush()
    return tenant
