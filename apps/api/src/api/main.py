import os
from contextlib import asynccontextmanager
from typing import Callable

import logfire
import sentry_sdk
import stripe
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.config import get_settings
from api.startup_check import check_env
from api.routers import (
    billing,
    brief_templates,
    c2pa,
    director_plans,
    dsr,
    engagement,
    exports,
    health,
    jobs,
    renders,
    uploads,
    webhooks,
    ws_jobs,
)


# ── Rate limiter (keyed by tenant bearer token, falls back to IP) ─────────────


def _rate_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        # Use first 32 chars of token as key — no decoding required
        return auth[7:39]
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_key, default_limits=["120/minute"])


# ── Observability ─────────────────────────────────────────────────────────────


def _init_observability(settings) -> None:
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            release=os.environ.get("GIT_SHA", "dev"),
            traces_sample_rate=0.1,
            environment=settings.env,
        )
    if settings.logfire_token:
        logfire.configure(token=settings.logfire_token, service_name="aidirector-api")
        logfire.instrument_fastapi()
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    check_env(settings)
    _init_observability(settings)
    yield


# ── Security headers middleware ───────────────────────────────────────────────


class SecurityHeadersMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"x-content-type-options"] = b"nosniff"
                headers[b"x-frame-options"] = b"DENY"
                headers[b"referrer-policy"] = b"strict-origin-when-cross-origin"
                headers[b"permissions-policy"] = b"camera=(), microphone=(), geolocation=()"
                headers[b"x-xss-protection"] = b"1; mode=block"
                message = {**message, "headers": list(headers.items())}
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ── Request ID middleware ─────────────────────────────────────────────────────

import uuid as _uuid


class RequestIDMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(_uuid.uuid4())
        scope["state"] = getattr(scope, "state", {})

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                headers[b"x-request-id"] = request_id.encode()
                message = {**message, "headers": list(headers.items())}
            await send(message)

        await self.app(scope, receive, send_with_id)


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI Director Agent",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.env != "production" else None,
        redoc_url="/redoc" if settings.env != "production" else None,
    )

    # Rate limiter state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware — applied bottom-up (last added = outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Idempotency-Key"],
        expose_headers=[
            "X-Request-ID",
            "X-Provenance-Manifest-Url",
            "X-Provenance-Key-Id",
            "X-Provenance-Public-Key",
            "X-Content-Credential",
            "X-Content-Credential-DID",
        ],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # Prometheus metrics (exposed at /metrics)
    Instrumentator().instrument(app).expose(app)

    # Routers (v1 — canonical prefix)
    app.include_router(health.router)
    app.include_router(uploads.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(director_plans.router, prefix="/api/v1")
    app.include_router(renders.router, prefix="/api/v1")
    app.include_router(brief_templates.router, prefix="/api/v1")
    app.include_router(exports.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(engagement.router, prefix="/api/v1")
    app.include_router(c2pa.router, prefix="/api/v1")
    app.include_router(dsr.router, prefix="/api/v1")
    app.include_router(webhooks.router, prefix="/api/v1")
    app.include_router(ws_jobs.router)

    # Legacy /api/ prefix (backward-compatible until all clients migrate to v1)
    app.include_router(uploads.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(director_plans.router, prefix="/api")
    app.include_router(renders.router, prefix="/api")
    app.include_router(brief_templates.router, prefix="/api")
    app.include_router(exports.router, prefix="/api")
    app.include_router(billing.router, prefix="/api")
    app.include_router(engagement.router, prefix="/api")
    app.include_router(c2pa.router, prefix="/api")
    app.include_router(dsr.router, prefix="/api")
    app.include_router(webhooks.router, prefix="/api")

    return app


app = create_app()
