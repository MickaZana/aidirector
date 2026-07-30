from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import ClerkClaims, verify_clerk_jwt
from api.db import get_db
from api.models import Tenant
from api.services.tenancy import get_or_create_tenant


def require_claims(authorization: Annotated[str | None, Header()] = None) -> ClerkClaims:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    return verify_clerk_jwt(token)


def require_tenant_id(claims: Annotated[ClerkClaims, Depends(require_claims)]) -> str:
    return claims.tenant_id


def require_tenant_row(
    db: Annotated[Session, Depends(get_db)],
    claims: Annotated[ClerkClaims, Depends(require_claims)],
) -> Tenant:
    return get_or_create_tenant(db, claims)


def require_admin(claims: Annotated[ClerkClaims, Depends(require_claims)]):
    if claims.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return claims


DbSession = Annotated[Session, Depends(get_db)]
Tenant_ = Annotated[str, Depends(require_tenant_id)]
TenantRow = Annotated[Tenant, Depends(require_tenant_row)]
Claims = Annotated[ClerkClaims, Depends(require_claims)]
AdminClaims = Annotated[ClerkClaims, Depends(require_admin)]
