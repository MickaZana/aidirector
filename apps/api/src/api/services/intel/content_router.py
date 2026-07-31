"""Routes content to intelligence without changing shared infrastructure."""
from __future__ import annotations

from api.content_types import ContentType, normalize_content_type
from api.services.intel.podcast_intelligence import ConversationSegment, analyze_segments


def analyze_content(content_type: str | None, upload_id: str, source_uri: str, *, transcript: list[ConversationSegment] | None = None):
    """Return content-specific analysis; Football remains on its existing adapter."""
    kind: ContentType = normalize_content_type(content_type)
    if kind == "podcast":
        if transcript is None:
            raise NotImplementedError("Podcast media analysis requires transcript/diarization input")
        result = analyze_segments(upload_id, transcript)
        return result, kind
    from api.services.intel.scene_analysis_adapter import analyze_video
    return analyze_video(upload_id, source_uri), kind
