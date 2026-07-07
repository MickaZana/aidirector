"""C2PA v2.3 compliance services.

Package components:
  - did_service:   DID:key generation + DID document management (R2-backed)
  - embedder:      FFmpeg-based manifest embedding into MP4 metadata
  - trust_anchor:  Trust anchor registration and verification (R2-backed)

Usage:
    from api.services.c2pa import embed_manifest, get_did_service, get_trust_anchor
"""

from __future__ import annotations

from api.services.c2pa.did_service import DidService, get_did_service
from api.services.c2pa.embedder import EmbedResult, embed_manifest
from api.services.c2pa.trust_anchor import TrustAnchorService, get_trust_anchor

__all__ = [
    "DidService",
    "EmbedResult",
    "TrustAnchorService",
    "embed_manifest",
    "get_did_service",
    "get_trust_anchor",
]
