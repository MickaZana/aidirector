"""Unit tests for webhook signature verification.

Tests verify that:
- Valid Clerk Svix signatures pass
- Tampered Clerk payloads return 400
- Missing CLERK_WEBHOOK_SECRET returns 500
- Valid Stripe signatures pass
- Tampered Stripe payloads return 400
- Missing STRIPE_WEBHOOK_SECRET returns 500
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_app(clerk_secret: str = "whsec_test123", stripe_secret: str = "whsec_stripe123"):
    """Create a test app with controlled settings."""
    from api.main import create_app
    return create_app()


def _svix_headers(secret: str, payload: bytes) -> dict:
    """Generate valid Svix webhook headers for testing."""
    msg_id = "msg_test_123"
    timestamp = str(int(time.time()))
    to_sign = f"{msg_id}.{timestamp}.{payload.decode()}".encode()

    # Svix secrets are base64-encoded; for testing use a simple HMAC
    sig = hmac.new(secret.encode(), to_sign, hashlib.sha256).hexdigest()
    return {
        "svix-id": msg_id,
        "svix-timestamp": timestamp,
        "svix-signature": f"v1,{sig}",
        "content-type": "application/json",
    }


# ── Clerk webhook tests ───────────────────────────────────────────────────────

class TestClerkWebhook:
    def test_missing_secret_returns_500(self):
        """When CLERK_WEBHOOK_SECRET is unset, reject with 500."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routers.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.clerk_webhook_secret = ""
            mock_settings.return_value = settings

            resp = client.post(
                "/api/webhooks/clerk",
                content=b'{"type":"user.created","data":{}}',
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 500

    def test_bad_signature_returns_400(self):
        """Tampered payload (wrong signature) must return 400."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        payload = b'{"type":"user.created","data":{"id":"usr_123"}}'

        with patch("api.routers.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.clerk_webhook_secret = "whsec_realsecret"
            mock_settings.return_value = settings

            resp = client.post(
                "/api/webhooks/clerk",
                content=payload,
                headers={
                    "content-type": "application/json",
                    "svix-id": "msg_fake",
                    "svix-timestamp": str(int(time.time())),
                    "svix-signature": "v1,invalidsignature",
                },
            )
        assert resp.status_code == 400
        assert "signature" in resp.json()["detail"].lower()

    def test_valid_user_created_accepted(self):
        """A properly signed Clerk user.created event processes without DB error."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        payload_data = {
            "type": "user.created",
            "data": {
                "id": "usr_abc123",
                "email_addresses": [{"email_address": "test@example.com"}],
                "primary_organization_id": None,
            },
        }
        payload = json.dumps(payload_data).encode()

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.Webhook") as mock_wh_class, \
             patch("api.routers.webhooks.get_db") as mock_get_db:

            settings = MagicMock()
            settings.clerk_webhook_secret = "whsec_valid"
            mock_settings.return_value = settings

            mock_wh = MagicMock()
            mock_wh.verify.return_value = payload_data
            mock_wh_class.return_value = mock_wh

            mock_db = MagicMock()
            mock_db.execute.return_value.scalar_one_or_none.return_value = None
            mock_get_db.return_value = iter([mock_db])

            resp = client.post(
                "/api/webhooks/clerk",
                content=payload,
                headers={"content-type": "application/json",
                         "svix-id": "msg_1", "svix-timestamp": "1", "svix-signature": "v1,x"},
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": "true"}

    def test_user_deleted_event_accepted(self):
        """user.deleted event is handled without error."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        payload_data = {"type": "user.deleted", "data": {"id": "usr_gone"}}
        payload = json.dumps(payload_data).encode()

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.Webhook") as mock_wh_class, \
             patch("api.routers.webhooks.get_db") as mock_get_db:

            settings = MagicMock()
            settings.clerk_webhook_secret = "whsec_valid"
            mock_settings.return_value = settings

            mock_wh = MagicMock()
            mock_wh.verify.return_value = payload_data
            mock_wh_class.return_value = mock_wh

            mock_db = MagicMock()
            mock_db.execute.return_value.scalar_one_or_none.return_value = None
            mock_get_db.return_value = iter([mock_db])

            resp = client.post(
                "/api/webhooks/clerk",
                content=payload,
                headers={"content-type": "application/json",
                         "svix-id": "msg_2", "svix-timestamp": "1", "svix-signature": "v1,x"},
            )

        assert resp.status_code == 200

    def test_unknown_event_type_still_returns_200(self):
        """Unknown event types should be ignored, not crash."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        payload_data = {"type": "session.created", "data": {}}
        payload = json.dumps(payload_data).encode()

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.Webhook") as mock_wh_class, \
             patch("api.routers.webhooks.get_db") as mock_get_db:

            settings = MagicMock()
            settings.clerk_webhook_secret = "whsec_valid"
            mock_settings.return_value = settings

            mock_wh = MagicMock()
            mock_wh.verify.return_value = payload_data
            mock_wh_class.return_value = mock_wh

            mock_db = MagicMock()
            mock_get_db.return_value = iter([mock_db])

            resp = client.post(
                "/api/webhooks/clerk",
                content=payload,
                headers={"content-type": "application/json",
                         "svix-id": "msg_3", "svix-timestamp": "1", "svix-signature": "v1,x"},
            )

        assert resp.status_code == 200


# ── Stripe webhook tests ──────────────────────────────────────────────────────

class TestStripeWebhook:
    def test_missing_secret_returns_500(self):
        """When STRIPE_WEBHOOK_SECRET is unset, reject with 500."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routers.webhooks.get_settings") as mock_settings:
            settings = MagicMock()
            settings.stripe_webhook_secret = ""
            mock_settings.return_value = settings

            resp = client.post(
                "/api/webhooks/stripe",
                content=b'{"type":"invoice.payment_succeeded"}',
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 500

    def test_bad_signature_returns_400(self):
        """Invalid Stripe-Signature header must return 400."""
        import stripe as stripe_lib
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.stripe") as mock_stripe:

            settings = MagicMock()
            settings.stripe_webhook_secret = "whsec_real"
            mock_settings.return_value = settings

            mock_stripe.Webhook.construct_event.side_effect = \
                stripe_lib.SignatureVerificationError("bad sig", "sig_header")

            resp = client.post(
                "/api/webhooks/stripe",
                content=b'{"type":"invoice.payment_succeeded"}',
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=fake,v1=fake",
                },
            )

        assert resp.status_code == 400
        assert "stripe" in resp.json()["detail"].lower()

    def test_valid_payment_succeeded_accepted(self):
        """A valid invoice.payment_succeeded event returns 200."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        event = {
            "type": "invoice.payment_succeeded",
            "data": {"object": {"customer": "cus_123", "amount_paid": 4900}},
        }

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.stripe") as mock_stripe:

            settings = MagicMock()
            settings.stripe_webhook_secret = "whsec_real"
            mock_settings.return_value = settings
            mock_stripe.Webhook.construct_event.return_value = event

            resp = client.post(
                "/api/webhooks/stripe",
                content=json.dumps(event).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=1,v1=valid",
                },
            )

        assert resp.status_code == 200
        assert resp.json() == {"received": "true"}

    def test_subscription_deleted_accepted(self):
        """customer.subscription.deleted is processed without error."""
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        event = {
            "type": "customer.subscription.deleted",
            "data": {"object": {"customer": "cus_456", "status": "canceled"}},
        }

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.stripe") as mock_stripe:

            settings = MagicMock()
            settings.stripe_webhook_secret = "whsec_real"
            mock_settings.return_value = settings
            mock_stripe.Webhook.construct_event.return_value = event

            resp = client.post(
                "/api/webhooks/stripe",
                content=json.dumps(event).encode(),
                headers={
                    "content-type": "application/json",
                    "stripe-signature": "t=1,v1=valid",
                },
            )

        assert resp.status_code == 200

    def test_replay_attack_rejected(self):
        """Stripe rejects stale timestamps — verify our handler propagates 400."""
        import stripe as stripe_lib
        from api.main import create_app
        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        with patch("api.routers.webhooks.get_settings") as mock_settings, \
             patch("api.routers.webhooks.stripe") as mock_stripe:

            settings = MagicMock()
            settings.stripe_webhook_secret = "whsec_real"
            mock_settings.return_value = settings

            # Stripe raises this on stale timestamp
            mock_stripe.Webhook.construct_event.side_effect = \
                stripe_lib.SignatureVerificationError("Timestamp outside tolerance", "sig")

            resp = client.post(
                "/api/webhooks/stripe",
                content=b'{}',
                headers={
                    "content-type": "application/json",
                    "stripe-signature": f"t={int(time.time()) - 400},v1=stale",
                },
            )

        assert resp.status_code == 400
