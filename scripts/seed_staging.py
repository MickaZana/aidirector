#!/usr/bin/env python
"""Seed script for staging/demo validation.

Creates 1 demo tenant, verifies `/health` returns ok, and optionally
runs a smoke test pipeline. Called from deploy runbook after
`alembic upgrade head`.

Usage:
    python scripts/seed_staging.py [--create-tenant] [--smoke-test]

Without flags, runs quick health checks only.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("seed_staging")


def check_health() -> bool:
    """Verify all health endpoints return ok."""
    import httpx

    base = "http://localhost:8000"
    ok = True
    for path in ["/health", "/health/db", "/health/queue"]:
        try:
            r = httpx.get(f"{base}{path}", timeout=10)
            data = r.json()
            status = data.get("status", "error")
            if status != "ok":
                log.warning("  %s → status=%s", path, status)
                ok = False
            else:
                log.info("  %s → ok", path)
        except Exception as exc:
            log.error("  %s → FAILED: %s", path, exc)
            ok = False
    return ok


def create_demo_tenant() -> bool:
    """Create a demo tenant with a known slug and plan."""
    from sqlalchemy import select
    from api.db import SessionLocal
    from api.models.tenancy import Tenant

    if SessionLocal is None:
        log.error("DATABASE_URL not configured — cannot create tenant")
        return False

    with SessionLocal() as db:
        existing = db.execute(
            select(Tenant).where(Tenant.slug == "demo-staging")
        ).scalar_one_or_none()
        if existing:
            log.info("  demo tenant already exists: id=%s plan=%s", existing.id, existing.plan)
            return True

        tenant = Tenant(
            id=uuid.uuid4(),
            slug="demo-staging",
            name="Demo Staging Tenant",
            plan="studio",  # unlimited — no quota issues
            settings={"demo": True, "created_by": "seed_staging"},
        )
        db.add(tenant)
        db.commit()
        log.info("  created demo tenant: id=%s slug=%s", tenant.id, tenant.slug)
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed staging environment")
    parser.add_argument("--create-tenant", action="store_true", help="Create demo tenant row")
    parser.add_argument("--smoke-test", action="store_true", help="Run full pipeline smoke test")
    args = parser.parse_args()

    log.info("═══ Seed staging ═══")

    # Always check health first
    log.info("▸ Health checks...")
    healthy = check_health()
    if not healthy:
        log.error("Health checks failed — aborting. Fix the API before seeding.")
        sys.exit(1)

    if args.create_tenant:
        log.info("▸ Creating demo tenant...")
        if not create_demo_tenant():
            log.error("Failed to create demo tenant.")
            sys.exit(1)

    if args.smoke_test:
        log.info("▸ Smoke test...")
        # Run the integration test if SOURCE_VIDEO is set
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/integration/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            log.info("  smoke test PASSED")
        else:
            log.error("  smoke test FAILED:\n%s", result.stdout + result.stderr)
            sys.exit(1)

    log.info("✓ Seed staging complete.")


if __name__ == "__main__":
    main()
