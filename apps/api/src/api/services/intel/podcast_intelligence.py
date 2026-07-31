"""Deterministic conversation intelligence.

The adapter is deliberately media-provider agnostic. A transcription/diarization
provider can later supply richer segments without changing the scoring contract.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from api.services.intel.capability_registry import SceneRecord, CandidateRecord


@dataclass(frozen=True)
class ConversationSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class ConversationAnalysis:
    scenes: list[SceneRecord]
    candidates: list[CandidateRecord]
    speakers: tuple[str, ...]


_HOOK_WORDS = re.compile(r"\b(why|how|never|always|secret|truth|learned|mistake|important|believe|surprising)\b", re.I)


def analyze_segments(upload_id: str, segments: Iterable[ConversationSegment]) -> ConversationAnalysis:
    """Create traceable scenes and ranked candidates from transcript segments."""
    rows = list(segments)
    speakers = tuple(dict.fromkeys(s.speaker for s in rows if s.speaker))
    scenes: list[SceneRecord] = []
    candidates: list[CandidateRecord] = []
    for index, segment in enumerate(rows):
        text = " ".join(segment.text.split())
        if not text or segment.end <= segment.start:
            continue
        words = len(text.split())
        hook = bool(_HOOK_WORDS.search(text))
        question = "?" in text
        duration = segment.end - segment.start
        concise = 0.55 <= duration <= 45 and words >= 5
        score = min(1.0, 0.25 + (0.2 if hook else 0) + (0.15 if question else 0) + (0.2 if concise else 0) + min(words, 40) / 200)
        kind = "question_answer" if question else "strong_statement" if hook else "conversation_moment"
        signals = {"content_type": "podcast", "speaker": segment.speaker, "word_count": words, "hook": hook, "question": question}
        scenes.append(SceneRecord(t_start=segment.start, t_end=segment.end, kind=kind, arc_position="hook" if index == 0 else "body", intensity=score, importance=score, signals=signals))
        candidates.append(CandidateRecord(scene_index=index, t_start=segment.start, t_end=segment.end, confidence_score=score, quality_score=min(1.0, 0.5 + score / 2), platform_score=score, rationale=f"conversation score={score:.2f}; {kind}; speaker={segment.speaker or 'unknown'}", scores={"content_type": "podcast", "conversation_score": score, "speaker": segment.speaker, "kind": kind}))
    candidates.sort(key=lambda c: float(c.scores.get("conversation_score", 0)), reverse=True)
    return ConversationAnalysis(scenes=scenes, candidates=candidates, speakers=speakers)


def podcast_render_preferences() -> dict[str, str | bool]:
    return {"caption_style": "documentary", "render_style": "conversation", "crop_strategy": "smart", "normalize_audio": False, "thumbnail_strategy": "speaker_frame", "content_type": "podcast"}
