"""Startup environment validation.

Called once from the FastAPI lifespan before the server accepts traffic.
Groups env vars by severity:

  CRITICAL — app cannot function without these; raises RuntimeError so the
             process exits with a non-zero code and the orchestrator restarts.
  WARN     — app degrades gracefully but ops should be alerted.

Keep this file free of heavy imports so it runs fast on cold starts.
"""

from __future__ import annotations

import logging
import shutil

log = logging.getLogger(__name__)

_CRITICAL: list[tuple[str, str]] = [
    ("DATABASE_URL", "Postgres connection string — all DB operations fail without it"),
    ("REDIS_URL", "Redis URL — job queue and idempotency unavailable without it"),
    ("CLERK_SECRET_KEY", "Clerk auth — all authenticated endpoints return 401"),
    ("CLERK_PUBLISHABLE_KEY", "Clerk auth — frontend cannot initialise Clerk"),
]

_WARN: list[tuple[str, str]] = [
    ("R2_ACCOUNT_ID", "Cloudflare R2 — uploads and exports will fail"),
    ("R2_ACCESS_KEY_ID", "Cloudflare R2 — uploads and exports will fail"),
    ("R2_SECRET_ACCESS_KEY", "Cloudflare R2 — uploads and exports will fail"),
    ("R2_BUCKET", "Cloudflare R2 — uploads and exports will fail"),
    ("STRIPE_SECRET_KEY", "Stripe — billing endpoints will fail"),
    ("STRIPE_WEBHOOK_SECRET", "Stripe — webhook validation will reject all events"),
    ("CLERK_WEBHOOK_SECRET", "Clerk webhook — tenant sync will silently fail until a public endpoint exists"),
    ("ANTHROPIC_API_KEY", "Director Agent — AI plan generation unavailable"),
    ("PROVENANCE_SIGNING_KEY_B64", "Provenance — rendered clips will not be signed"),
    ("SENTRY_DSN", "Error tracking disabled — production errors will be silent"),
    ("LOGFIRE_TOKEN", "Structured logging disabled — reduced observability"),
]


def check_env(settings) -> None:
    """Validate settings at startup. Logs warnings; raises on critical gaps."""
    missing_critical: list[str] = []

    for var, description in _CRITICAL:
        value = getattr(settings, var.lower(), "") or ""
        if not value.strip():
            missing_critical.append(f"  {var}: {description}")

    if missing_critical:
        msg = "STARTUP ABORTED — missing critical environment variables:\n" + "\n".join(
            missing_critical
        )
        log.critical(msg)
        raise RuntimeError(msg)

    for var, description in _WARN:
        value = getattr(settings, var.lower(), "") or ""
        if not value.strip():
            log.warning("startup_check: %s not set — %s", var, description)

    # FFmpeg check
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        log.info("startup_check: ffmpeg found at %s", ffmpeg_path)
    else:
        log.warning("startup_check: ffmpeg not found on PATH — renders will fail")

    log.info("startup_check: all critical env vars present")
