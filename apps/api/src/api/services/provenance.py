"""Ed25519 provenance signing — C2PA v2.3 compliant.

Every rendered clip gets a signed manifest that proves:
  - which source video it came from (source_uri)
  - the exact clip window (clip_start_s, clip_end_s)
  - which tenant requested it
  - which renderer produced it
  - the content hash of the final C2PA-embedded MP4

The manifest follows C2PA v2.3 field names (assertions, signature, metadata,
did, credential) so upgrading to the full c2pa-python library is a drop-in
swap for the embedding step only.

Key lifecycle:
  - On first `from_env()`, the public key is registered in the self-hosted
    C2PA trust anchor (R2) and a DID document (did:key) is published.
  - Rotating the key via env var updates the trust anchor and preserves
    the old key's history as "rotated".

Usage:
    signer = ProvSigner.from_env()
    manifest = signer.sign_manifest(assertion)
    manifest.model_dump(mode="json")        # ready to attach to API response
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

from api.schemas.provenance_manifest import (
    ProvenanceManifest,
    RenderAssertion,
    SigningMetadata,
)

log = logging.getLogger(__name__)


class ProvSigner:
    """Ed25519 signer — one instance per process, loaded from env.

    On construction, the key is automatically registered with the C2PA
    trust anchor and a DID document is published to R2.
    """

    def __init__(self, private_key_b64: str, key_id: str) -> None:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

        raw = base64.b64decode(private_key_b64)
        self._private_key: Ed25519PrivateKey = Ed25519PrivateKey.from_private_bytes(raw)
        self._public_key = self._private_key.public_key()
        self.key_id = key_id

        # C2PA v2.3: register with trust anchor and publish DID on init
        self._did: str | None = None
        self._credential_url: str | None = None
        self._init_c2pa()

    def _init_c2pa(self) -> None:
        """Register key with trust anchor + publish DID document.

        Failures are logged but not raised — the signer works without
        C2PA infrastructure (no DID/credential), just with reduced
        compliance. This matches the codebase philosophy of graceful
        degradation (Sprint 2).
        """
        try:
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                PublicFormat,
            )

            from api.services.c2pa import get_did_service, get_trust_anchor

            pub_bytes = self._public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            pub_b64 = base64.b64encode(pub_bytes).decode("ascii")

            # 1. Get or create DID
            did_svc = get_did_service()
            self._did = did_svc.get_or_create_did(pub_bytes)

            # 2. Register with trust anchor
            ta = get_trust_anchor()
            entry = ta.register_key(
                key_id=self.key_id,
                did=self._did,
                public_key_b64=pub_b64,
            )

            # 3. Credential URL = trust anchor registry URL + DID doc URL
            #    Per C2PA v2.3, the credential field points to a resolvable
            #    document that proves the key's trust status.
            self._credential_url = did_svc.get_did_document_url(self._did)

            log.info(
                "prov_signer: C2PA initialized key_id=%s did=%s",
                self.key_id,
                self._did,
            )
        except Exception as exc:
            log.warning("prov_signer: C2PA init skipped (graceful degradation): %s", exc)

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
                'Generate with: python -c "import os, base64; '
                "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; "
                "k=Ed25519PrivateKey.generate(); "
                'print(base64.b64encode(k.private_bytes_raw()).decode())"'
            )
        return cls(key_b64, key_id)

    def sign_manifest(
        self,
        assertion: RenderAssertion,
        *,
        content_hash: str | None = None,
    ) -> ProvenanceManifest:
        """Sign a single render assertion and return a complete ProvenanceManifest.

        Args:
            assertion: The render claim to sign.
            content_hash: Optional sha256 hex of the C2PA-embedded MP4 bytes.
                          When provided, it's included in the assertion so the
                          manifest's payload_hash covers the content identity.
        """
        from cryptography.hazmat.primitives.asymmetric.utils import (
            decode_dss_signature,
        )

        # Set content hash on the assertion if provided
        if content_hash:
            assertion.content_hash = content_hash

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
                did=self._did,
                credential=self._credential_url,
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

    @property
    def did(self) -> str | None:
        """The DID (did:key) for this signer, if C2PA was initialized."""
        return self._did

    @property
    def credential_url(self) -> str | None:
        """The credential/trust-anchor URL for this signer, if initialized."""
        return self._credential_url


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
