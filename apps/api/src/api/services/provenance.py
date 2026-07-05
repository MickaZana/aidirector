"""Ed25519 provenance signing for rendered clip artifacts.

Every rendered clip gets a signed manifest that proves:
  - which source video it came from (source_uri)
  - the exact clip window (clip_start_s, clip_end_s)
  - which tenant requested it
  - which renderer produced it

The manifest JSON follows C2PA top-level field names (assertions, signature,
metadata) so upgrading to the full c2pa-python library is a drop-in swap.

Usage:
    signer = ProvSigner.from_env()          # reads PROVENANCE_SIGNING_KEY_B64
    manifest = signer.sign_manifest(assertion)
    manifest.model_dump(mode="json")        # ready to attach to API response

Key rotation: set a new PROVENANCE_SIGNING_KEY_B64 + PROVENANCE_KEY_ID.
Old manifests remain verifiable with their key_id recorded in metadata.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone

from api.schemas.provenance_manifest import (
    ProvenanceManifest,
    RenderAssertion,
    SigningMetadata,
)


class ProvSigner:
    """Ed25519 signer — one instance per process, loaded from env."""

    def __init__(self, private_key_b64: str, key_id: str) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        raw = base64.b64decode(private_key_b64)
        self._private_key: Ed25519PrivateKey = Ed25519PrivateKey.from_private_bytes(raw)
        self._public_key = self._private_key.public_key()
        self.key_id = key_id

    @classmethod
    def from_env(cls) -> "ProvSigner":
        """Construct from env vars PROVENANCE_SIGNING_KEY_B64 + PROVENANCE_KEY_ID.

        Raises RuntimeError when env vars are absent so misconfigured deploys
        fail loudly at startup rather than silently producing unsigned manifests.
        """
        key_b64 = os.environ.get("PROVENANCE_SIGNING_KEY_B64", "")
        key_id = os.environ.get("PROVENANCE_KEY_ID", "default-v1")
        if not key_b64:
            raise RuntimeError(
                "PROVENANCE_SIGNING_KEY_B64 is not set. "
                "Generate with: python -c \"import os, base64; "
                "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; "
                "k=Ed25519PrivateKey.generate(); "
                "print(base64.b64encode(k.private_bytes_raw()).decode())\""
            )
        return cls(key_b64, key_id)

    def sign_manifest(self, assertion: RenderAssertion) -> ProvenanceManifest:
        """Sign a single render assertion and return a complete ProvenanceManifest."""
        from cryptography.hazmat.primitives.asymmetric.utils import (
            decode_dss_signature,
        )

        # Canonical JSON: sorted keys, no whitespace — deterministic across
        # Python versions. This is the bytes that the signature covers.
        payload_bytes = json.dumps(
            assertion.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        raw_sig = self._private_key.sign(payload_bytes)
        signature_b64 = base64.urlsafe_b64encode(raw_sig).decode("ascii")

        return ProvenanceManifest(
            assertions=[assertion],
            signature=signature_b64,
            payload_hash=payload_hash,
            metadata=SigningMetadata(
                signer="ed25519",
                key_id=self.key_id,
                signed_at=datetime.now(timezone.utc).isoformat(),
            ),
        )

    def verify(self, manifest: ProvenanceManifest) -> bool:
        """Verify the manifest's signature against its assertions. Returns bool."""
        from cryptography.exceptions import InvalidSignature

        try:
            assertion = manifest.assertions[0]
            payload_bytes = json.dumps(
                assertion.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            sig_bytes = base64.urlsafe_b64decode(manifest.signature)
            self._public_key.verify(sig_bytes, payload_bytes)
            # Also verify the hash hasn't been tampered with.
            expected_hash = hashlib.sha256(payload_bytes).hexdigest()
            return expected_hash == manifest.payload_hash
        except (InvalidSignature, Exception):
            return False

    def public_key_b64(self) -> str:
        """Return the base64-encoded raw public key for out-of-band verification."""
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        raw = self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return base64.b64encode(raw).decode("ascii")


def assertion_from_manifest(manifest) -> RenderAssertion:
    """Build a RenderAssertion from a RenderManifest (the render schema object)."""
    return RenderAssertion(
        source_uri=manifest.source_uri,
        clip_start_s=manifest.clip_start,
        clip_end_s=manifest.clip_end,
        renderer=manifest.renderer,
        platform=manifest.platform,
        tenant_id=manifest.tenant_id,
        candidate_id=manifest.candidate_id,
        render_job_id=manifest.render_job_id,
    )
