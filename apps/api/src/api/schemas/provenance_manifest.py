"""C2PA-shaped provenance manifest schema — v2 (C2PA v2.3 compatible).

Fields mirror the C2PA v2.3 JSON structure so an upgrade to the full
c2pa-python library is mechanical: swap the signer, keep the field names.

Reference: https://c2pa.org/specifications/specifications/2.3/specs/C2PA_Specification.html

Additions for v2:
  - `content_hash` in assertions: sha256 of the rendered MP4 bytes
  - `did` (Decentralized Identifier) in metadata: did:key derived from the
    Ed25519 public key so anyone can resolve the signer's key material
    from a DID document stored alongside the clip.
  - manifest_version bumped to "2"
  - `credential` field in metadata: URL of the trust anchor registration
    for C2PA Content Credentials verification.

Validation: instantiate with `ProvenanceManifest.model_validate(data)`.
The schema is intentionally strict (`extra="forbid"`) so a hand-crafted
manifest with extra fields doesn't silently pass validation.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RenderAssertion(BaseModel):
    """Claim about one rendered output asset.

    C2PA v2.3 mandates a `content_hash` so consumers can verify the
    asset bytes match what was signed, even after transport.
    """

    model_config = ConfigDict(extra="forbid")

    label: Literal["ai.director.render"] = "ai.director.render"
    source_uri: str
    clip_start_s: float
    clip_end_s: float
    renderer: str
    platform: str
    tenant_id: str
    candidate_id: str
    render_job_id: str
    content_hash: str | None = None
    """sha256 hex of the final C2PA-embedded MP4 bytes.

    Populated after the manifest is written into the file; the merkle
    root of the C2PA box covers this hash so tampering with the file
    after signing is detectable.
    """


class SigningMetadata(BaseModel):
    """Signer identity and C2PA v2.3 compliance metadata."""

    model_config = ConfigDict(extra="forbid")

    signer: Literal["ed25519"] = "ed25519"
    key_id: str
    did: str | None = None
    """Decentralized Identifier (did:key) for the signing key.

    Resolves to a DID document containing the public key, allowing
    any consumer to verify the signature without out-of-band key exchange.
    """
    credential: str | None = None
    """URL of the Content Credential / trust anchor registration.

    Points to a JSON document in R2 that records the DID, key_id,
    first-seen timestamp, and trust level. Consumers follow this URL
    to verify the signer is a known AI Director instance.
    """
    signed_at: str  # ISO-8601 UTC
    manifest_version: Literal["2"] = "2"
    """Bumped from '1' to '2' for C2PA v2.3 compliance.

    v1 manifests (sidecar-only, no content_hash, no DID) remain
    verifiable via the `key_id` recorded in their metadata.
    """


class ProvenanceManifest(BaseModel):
    """Top-level C2PA-shaped manifest. One per rendered clip."""

    model_config = ConfigDict(extra="forbid")

    assertions: list[RenderAssertion] = Field(min_length=1)
    signature: str  # base64url Ed25519 signature
    metadata: SigningMetadata
    payload_hash: str  # sha256 hex of the canonical assertion JSON
