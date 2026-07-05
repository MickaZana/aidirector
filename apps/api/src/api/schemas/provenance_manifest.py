"""C2PA-shaped provenance manifest schema.

Fields mirror the C2PA top-level JSON structure so an upgrade to the full
c2pa-python library is mechanical: swap the signer, keep the field names.

Reference: https://c2pa.org/specifications/specifications/1.4/specs/C2PA_Specification.html
  - assertions: list of claim objects (what happened to this asset)
  - signature:  base64url-encoded Ed25519 signature over sha256(canonical JSON)
  - metadata:   signer identity + timestamps

Validation: instantiate with `ProvenanceManifest.model_validate(data)`.
The schema is intentionally strict (`extra="forbid"`) so a hand-crafted
manifest with extra fields doesn't silently pass validation.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RenderAssertion(BaseModel):
    """Claim about one rendered output asset."""
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


class SigningMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signer: Literal["ed25519"] = "ed25519"
    key_id: str
    signed_at: str      # ISO-8601 UTC
    manifest_version: Literal["1"] = "1"


class ProvenanceManifest(BaseModel):
    """Top-level C2PA-shaped manifest. One per rendered clip."""
    model_config = ConfigDict(extra="forbid")

    assertions: list[RenderAssertion] = Field(min_length=1)
    signature: str        # base64url Ed25519 signature
    metadata: SigningMetadata
    payload_hash: str     # sha256 hex of the canonical assertion JSON
