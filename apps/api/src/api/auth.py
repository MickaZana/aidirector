"""Clerk JWT verification.

Clerk issues short-lived JWTs signed with keys served at the configured JWKS URL.
We verify the signature, check `iss` and `exp`, and extract the user id (`sub`) and
the active organization id (`org_id`) which we use as our `tenant_id`.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from api.config import get_settings


@dataclass
class ClerkClaims:
    user_id: str
    tenant_id: str  # Clerk org_id, or `user_<id>` for personal tenants
    email: str | None
    role: str | None = None


_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        settings = get_settings()
        if not settings.clerk_jwks_url:
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Clerk JWKS not configured")
        _jwks_client = PyJWKClient(settings.clerk_jwks_url)
    return _jwks_client


def verify_clerk_jwt(token: str) -> ClerkClaims:
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"require": ["exp", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    user_id = payload["sub"]
    tenant_id = payload.get("org_id") or f"user_{user_id}"
    metadata = payload.get("metadata") or payload.get("public_metadata") or {}
    role = payload.get("role") or metadata.get("role")
    return ClerkClaims(user_id=user_id, tenant_id=tenant_id, email=payload.get("email"), role=role)
