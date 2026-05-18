from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.auth import ClerkClaims, verify_clerk_jwt
from api.db import get_db


def require_claims(authorization: Annotated[str | None, Header()] = None) -> ClerkClaims:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1]
    return verify_clerk_jwt(token)


def require_tenant(claims: Annotated[ClerkClaims, Depends(require_claims)]) -> str:
    return claims.tenant_id


DbSession = Annotated[Session, Depends(get_db)]
Tenant = Annotated[str, Depends(require_tenant)]
Claims = Annotated[ClerkClaims, Depends(require_claims)]
