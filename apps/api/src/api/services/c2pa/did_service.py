"""DID (Decentralized Identifier) service — did:key method.

Generates a `did:key` from an Ed25519 public key and manages a DID document
stored in R2 so that any consumer can resolve the signer's public key.

The `did:key` method encodes the raw public key bytes directly in the DID
string using multicodec + multibase, so the DID is self-describing and
resolvable without a blockchain or ledger.

Reference: https://w3c-ccg.github.io/did-method-key/

Usage:
    did_service = get_did_service()
    did = did_service.get_or_create_did(public_key_bytes)
    doc = did_service.get_did_document(did)
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from api.config import get_settings
from api.services import r2

log = logging.getLogger(__name__)

# ── DID:key multicodec constants ──────────────────────────────────────────────
# Ed25519 public key multicodec prefix: 0xed (varint-encoded as 0xed, 0x01)
# See https://github.com/multiformats/multicodec
_ED25519_PUBLIC_KEY_PREFIX = bytes([0xED, 0x01])

# R2 key prefix for DID documents
_DID_DOC_PREFIX = "_c2pa/did/"
_DID_DOC_CACHE_TTL_S = 300  # 5 min in-memory cache for DID document


class DidService:
    """Manages DID:key generation and DID document storage.

    Thread-safe (no mutable shared state after __init__). Designed as a
    singleton per process — instantiate via `get_did_service()`.
    """

    def __init__(self, settings=None) -> None:
        self._settings = settings or get_settings()
        self._did_cache: dict[str, str] = {}  # public_key_b64 → did:key string
        self._doc_cache: dict[str, dict] = {}  # did:key → DID document dict
        self._doc_cache_ts: float = 0.0

    # ── Public API ─────────────────────────────────────────────────────────

    def get_or_create_did(self, public_key_bytes: bytes) -> str:
        """Return a `did:key` for the given Ed25519 public key.

        If the key has been seen before in this process, the cached DID is
        returned. Otherwise a new DID is computed and persisted to R2.
        """
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        # Normalize to raw bytes
        if hasattr(public_key_bytes, "public_bytes"):
            public_key_bytes = public_key_bytes.public_bytes(Encoding.Raw, PublicFormat.Raw)

        import base64

        key_b64 = base64.b64encode(public_key_bytes).decode("ascii")

        if key_b64 in self._did_cache:
            return self._did_cache[key_b64]

        did = self._build_did_key(public_key_bytes)
        # Persist DID document to R2
        self._ensure_did_document(did, public_key_bytes)

        self._did_cache[key_b64] = did
        return did

    def get_did_document(self, did: str) -> dict[str, Any] | None:
        """Resolve a `did:key` to its DID document.

        Looks in R2 first, falls back to local cache. Returns None if the
        document hasn't been registered (unusual — `get_or_create_did` always
        writes one).
        """
        # Check local cache first
        now = time.monotonic()
        if self._doc_cache and (now - self._doc_cache_ts) < _DID_DOC_CACHE_TTL_S:
            return self._doc_cache.get(did)

        # Fetch from R2
        doc_key = f"{_DID_DOC_PREFIX}{did}.json"
        try:
            doc_bytes = r2.get_object(doc_key)
            if doc_bytes:
                doc = json.loads(doc_bytes)
                self._doc_cache[did] = doc
                self._doc_cache_ts = now
                return doc
        except Exception:
            log.debug("did_service: failed to fetch DID document from R2 for %s", did)

        return None

    def get_did_document_url(self, did: str) -> str:
        """Return the publicly accessible URL for the DID document."""
        doc_key = f"{_DID_DOC_PREFIX}{did}.json"
        return r2.signed_get_url(doc_key, expires_s=86400)

    # ── Internals ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_did_key(public_key_bytes: bytes) -> str:
        """Build a `did:key` string from raw Ed25519 public key bytes.

        did:key encoding:
          1. Prepend multicodec prefix (0xed, 0x01) to public key bytes
          2. Encode as multibase base58-btc (prefix 'z')
          3. Prepend 'did:key:'
        """
        import base58

        combined = _ED25519_PUBLIC_KEY_PREFIX + public_key_bytes
        b58_encoded = base58.b58encode(combined).decode("ascii")
        return f"did:key:z{b58_encoded}"

    def _ensure_did_document(self, did: str, public_key_bytes: bytes) -> None:
        """Write DID document to R2 if it doesn't already exist."""
        doc_key = f"{_DID_DOC_PREFIX}{did}.json"

        # Check if already exists
        try:
            existing = r2.head_object(doc_key)
            if existing is not None:
                return  # Already registered
        except Exception:
            pass

        import base64

        pub_b64 = base64.b64encode(public_key_bytes).decode("ascii")

        doc = {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://w3id.org/security/multikey/v1",
            ],
            "id": did,
            "verificationMethod": [
                {
                    "id": f"{did}#key-1",
                    "type": "Multikey",
                    "controller": did,
                    "publicKeyMultibase": self._public_key_to_multibase(public_key_bytes),
                }
            ],
            "assertionMethod": [f"{did}#key-1"],
            "authentication": [f"{did}#key-1"],
        }

        try:
            doc_bytes = json.dumps(doc, indent=2).encode()
            self._put_to_r2(doc_key, doc_bytes)
            log.info("did_service: registered DID document for %s", did)
        except Exception as exc:
            log.error("did_service: failed to write DID document for %s: %s", did, exc)

    @staticmethod
    def _public_key_to_multibase(public_key_bytes: bytes) -> str:
        """Encode public key as multibase (base58-btc with multicodec prefix)."""
        import base58

        combined = _ED25519_PUBLIC_KEY_PREFIX + public_key_bytes
        return f"z{base58.b58encode(combined).decode('ascii')}"

    @staticmethod
    def _put_to_r2(key: str, body: bytes) -> None:
        """Write bytes to R2 (bypasses the r2.put_object abstraction).

        Uses the same boto3 client pattern as the rest of the codebase.
        """
        import boto3

        _s = get_settings()
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{_s.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=_s.r2_access_key_id,
            aws_secret_access_key=_s.r2_secret_access_key,
        )
        client.put_object(
            Bucket=_s.r2_bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )


# ── Module-level singleton ─────────────────────────────────────────────────


_did_service: DidService | None = None


def get_did_service(settings=None) -> DidService:
    """Return the process-wide DidService singleton."""
    global _did_service
    if _did_service is None:
        _did_service = DidService(settings=settings)
    return _did_service
