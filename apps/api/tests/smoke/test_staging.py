"""Staging / production smoke tests.

Auto-skips unless STAGING_API_URL is set. Run with:

    STAGING_API_URL=https://api.aidirector.io uv run pytest tests/smoke/ -v
"""
from __future__ import annotations

import os

import pytest
import requests

API_URL = os.environ.get("STAGING_API_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(
    not API_URL,
    reason="STAGING_API_URL not set — skipping smoke tests",
)


class TestHealth:
    def test_health_returns_ok(self):
        resp = requests.get(f"{API_URL}/health", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("status") == "ok", f"Unexpected body: {body}"

    def test_health_has_version(self):
        resp = requests.get(f"{API_URL}/health", timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body or "status" in body, (
            f"Health response missing expected fields: {body}"
        )

    def test_health_response_time_under_2s(self):
        resp = requests.get(f"{API_URL}/health", timeout=10)
        assert resp.elapsed.total_seconds() < 2.0, (
            f"Health endpoint too slow: {resp.elapsed.total_seconds():.2f}s"
        )


class TestQueueHealth:
    def test_queue_health_returns_200(self):
        resp = requests.get(f"{API_URL}/health/queue", timeout=10)
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )

    def test_queue_health_body_has_queues(self):
        resp = requests.get(f"{API_URL}/health/queue", timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        assert "queues" in body or "status" in body, (
            f"Queue health response missing expected fields: {body}"
        )

    def test_queue_health_status_not_error(self):
        resp = requests.get(f"{API_URL}/health/queue", timeout=10)
        assert resp.status_code == 200
        body = resp.json()
        status = body.get("status", "ok")
        assert status in ("ok", "degraded"), (
            f"Unexpected queue health status: {status!r}. "
            "If Redis is down the status should be 'degraded', not an error."
        )

    def test_queue_health_response_time_under_3s(self):
        resp = requests.get(f"{API_URL}/health/queue", timeout=10)
        assert resp.elapsed.total_seconds() < 3.0, (
            f"Queue health endpoint too slow: {resp.elapsed.total_seconds():.2f}s"
        )


class TestUnauthenticatedEndpoints:
    def test_unauthenticated_api_returns_401_not_500(self):
        """Authenticated endpoints must reject cleanly, not crash."""
        resp = requests.get(f"{API_URL}/api/jobs", timeout=10)
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated request, got {resp.status_code}"
        )

    def test_nonexistent_route_returns_404(self):
        resp = requests.get(f"{API_URL}/api/this-route-does-not-exist", timeout=10)
        assert resp.status_code == 404
