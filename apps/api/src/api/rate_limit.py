"""Shared rate limiter — split out from main.py so routers can import it
without a circular dependency (main.py imports the routers)."""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        # Use first 32 chars of token as key — no decoding required
        return auth[7:39]
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_key, default_limits=["120/minute"])
