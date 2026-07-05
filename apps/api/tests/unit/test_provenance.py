"""Unit tests for services/provenance.py and schemas/provenance_manifest.py"""
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from api.schemas.provenance_manifest import (
    ProvenanceManifest,
    RenderAssertion,
    SigningMetadata,
)
from api.services.provenance import ProvSigner, assertion_from_manifest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fresh_signer() -> ProvSigner:
    raw_key = Ed25519PrivateKey.generate().private_bytes_raw()
    key_b64 = base64.b64encode(raw_key).decode()
    return ProvSigner(key_b64, key_id="test-v1")


def _sample_assertion() -> RenderAssertion:
    return RenderAssertion(
        source_uri="r2://bucket/uploads/match.mp4",
        clip_start_s=10.0,
        clip_end_s=23.0,
        renderer="ffmpeg_basic",
        platform="youtube_shorts",
        tenant_id="tenant-abc",
        candidate_id="cand-001",
        render_job_id="rjob-001",
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestProvenanceManifestSchema:
    def test_valid_manifest_validates(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        # round-trip through model_validate
        data = manifest.model_dump(mode="json")
        recovered = ProvenanceManifest.model_validate(data)
        assert recovered.signature == manifest.signature

    def test_extra_fields_forbidden(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        data = manifest.model_dump(mode="json")
        data["unexpected_field"] = "oops"
        with pytest.raises(Exception):
            ProvenanceManifest.model_validate(data)

    def test_empty_assertions_rejected(self):
        with pytest.raises(Exception):
            ProvenanceManifest(
                assertions=[],
                signature="abc",
                payload_hash="def",
                metadata=SigningMetadata(key_id="k", signed_at="2026-01-01T00:00:00Z"),
            )

    def test_assertion_label_is_fixed(self):
        a = _sample_assertion()
        assert a.label == "ai.director.render"


# ---------------------------------------------------------------------------
# ProvSigner.sign_manifest
# ---------------------------------------------------------------------------

class TestProvSignerSign:
    def test_returns_provenance_manifest(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        assert isinstance(manifest, ProvenanceManifest)

    def test_signature_is_non_empty(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        assert len(manifest.signature) > 0

    def test_payload_hash_is_sha256_hex(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        assert len(manifest.payload_hash) == 64
        int(manifest.payload_hash, 16)  # must be valid hex

    def test_key_id_recorded_in_metadata(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        assert manifest.metadata.key_id == "test-v1"

    def test_same_assertion_same_hash(self):
        signer = _fresh_signer()
        a = _sample_assertion()
        h1 = signer.sign_manifest(a).payload_hash
        h2 = signer.sign_manifest(a).payload_hash
        assert h1 == h2

    def test_different_assertions_different_hash(self):
        signer = _fresh_signer()
        a1 = _sample_assertion()
        a2 = RenderAssertion(
            source_uri="r2://bucket/uploads/other.mp4",
            clip_start_s=5.0, clip_end_s=18.0,
            renderer="sports_hype", platform="tiktok",
            tenant_id="tenant-xyz", candidate_id="cand-002",
            render_job_id="rjob-002",
        )
        assert signer.sign_manifest(a1).payload_hash != signer.sign_manifest(a2).payload_hash


# ---------------------------------------------------------------------------
# ProvSigner.verify
# ---------------------------------------------------------------------------

class TestProvSignerVerify:
    def test_valid_manifest_verifies(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        assert signer.verify(manifest) is True

    def test_tampered_signature_fails(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        data = manifest.model_dump(mode="json")
        # flip one byte in the signature
        raw = base64.urlsafe_b64decode(data["signature"] + "==")
        raw = bytes([raw[0] ^ 0xFF]) + raw[1:]
        data["signature"] = base64.urlsafe_b64encode(raw).decode()
        bad = ProvenanceManifest.model_validate(data)
        assert signer.verify(bad) is False

    def test_tampered_hash_fails(self):
        signer = _fresh_signer()
        manifest = signer.sign_manifest(_sample_assertion())
        data = manifest.model_dump(mode="json")
        data["payload_hash"] = "a" * 64  # wrong hash
        bad = ProvenanceManifest.model_validate(data)
        assert signer.verify(bad) is False

    def test_wrong_key_cannot_verify(self):
        signer1 = _fresh_signer()
        signer2 = _fresh_signer()
        manifest = signer1.sign_manifest(_sample_assertion())
        assert signer2.verify(manifest) is False


# ---------------------------------------------------------------------------
# from_env
# ---------------------------------------------------------------------------

class TestProvSignerFromEnv:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("PROVENANCE_SIGNING_KEY_B64", raising=False)
        with pytest.raises(RuntimeError, match="PROVENANCE_SIGNING_KEY_B64"):
            ProvSigner.from_env()

    def test_valid_env_creates_signer(self, monkeypatch):
        raw = Ed25519PrivateKey.generate().private_bytes_raw()
        monkeypatch.setenv("PROVENANCE_SIGNING_KEY_B64", base64.b64encode(raw).decode())
        monkeypatch.setenv("PROVENANCE_KEY_ID", "env-test-v1")
        signer = ProvSigner.from_env()
        assert signer.key_id == "env-test-v1"


# ---------------------------------------------------------------------------
# assertion_from_manifest helper
# ---------------------------------------------------------------------------

class TestAssertionFromManifest:
    def test_fields_match(self):
        class FakeManifest:
            source_uri = "r2://x"
            clip_start = 1.0
            clip_end = 5.0
            renderer = "ffmpeg_basic"
            platform = "tiktok"
            tenant_id = "t1"
            candidate_id = "c1"
            render_job_id = "rj1"

        a = assertion_from_manifest(FakeManifest())
        assert a.source_uri == "r2://x"
        assert a.clip_start_s == 1.0
        assert a.clip_end_s == 5.0
        assert a.renderer == "ffmpeg_basic"
