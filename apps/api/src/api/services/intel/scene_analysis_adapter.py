"""Scene analysis adapter — the only AI Director module that imports OmegaClips.

Phase 2 integration: imports `football_pipeline.config.PipelineConfig`,
`football_pipeline.scoreboard.{normalize_ocr_text, parse_score,
ScoreboardChangeTracker}`, and `football_pipeline.models.ScoreboardState`.

These are real OmegaClips capabilities (capability_map IDs #1, #3 — both
status A). Feeding the change tracker a sequence of synthetic OCR reads
produces real `ConfirmedScoreChange` events that AI Director maps to
`SceneRecord`. No mocks — the function calls are production OmegaClips code.

For phase 3, replace the synthetic fixture path with the full orchestrator:
download R2 source → run `FootballPipelineOrchestrator.run_full_pipeline` →
parse `workspace/` artifacts → same SceneRecord output shape. The contract
the rest of AI Director sees does not change.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TypedDict

from api.services.intel.capability_registry import SceneAnalysisResult, SceneRecord
from api.services.intel.omega_client import is_populated, submodule_path, submodule_sha

# Ensure packages/intel is on sys.path so `football_pipeline.*` is importable
# in dev/local-probe contexts (Modal handles its own PYTHONPATH).
_INTEL_DIR = submodule_path()
if _INTEL_DIR.exists() and str(_INTEL_DIR) not in sys.path:
    sys.path.insert(0, str(_INTEL_DIR))


class OcrFixtureRead(TypedDict):
    """One synthetic 'OCR read' — what a frame's scoreboard text would say."""

    t: float
    raw_text: str
    ocr_confidence: float


def _build_scoreboard_state(read: OcrFixtureRead):
    """Use real OmegaClips parsing to build a ScoreboardState from raw OCR text."""
    from football_pipeline.models import ScoreboardState
    from football_pipeline.scoreboard import (
        CLOCK_PATTERN,
        normalize_ocr_text,
        parse_score,
    )

    normalized = normalize_ocr_text(read["raw_text"])
    home, away, parser_conf = parse_score(normalized)
    clock_match = CLOCK_PATTERN.search(normalized)
    clock_text = clock_match.group(0) if clock_match else None
    parse_valid = home is not None and away is not None

    return ScoreboardState(
        t=read["t"],
        home_score=home,
        away_score=away,
        clock_text=clock_text,
        raw_text=read["raw_text"],
        confidence=read["ocr_confidence"],
        normalized_text=normalized,
        parse_valid=parse_valid,
        parser_confidence=parser_conf,
        ocr_backend="fixture",
    )


def analyze_video(
    upload_id: str,
    source_uri: str,
    *,
    fixture_reads: list[OcrFixtureRead] | None = None,
) -> SceneAnalysisResult:
    """Run scene analysis for an upload.

    Phase 2 supports two modes:
      - `fixture_reads` provided → run real OmegaClips scoreboard parsing +
        change tracking over a synthetic OCR sequence (no video file required).
      - `fixture_reads` is None → raises NotImplementedError until phase 3
        wires the full orchestrator with R2 download.

    Returns SceneAnalysisResult with one SceneRecord per confirmed score change.
    """
    if not is_populated():
        raise RuntimeError(
            f"OmegaClips submodule not populated at {_INTEL_DIR}. "
            "Run `git submodule update --init --recursive`."
        )

    if fixture_reads is None:
        raise NotImplementedError(
            "Full-video analyze_video lives in phase 3. "
            "Pass fixture_reads=[...] for the phase-2 integration path."
        )

    from football_pipeline.config import PipelineConfig
    from football_pipeline.scoreboard import ScoreboardChangeTracker

    cfg = PipelineConfig()
    tracker = ScoreboardChangeTracker(
        hold_sec=cfg.scoreboard_change_hold_sec
        if hasattr(cfg, "scoreboard_change_hold_sec")
        else 4.0,
        min_confidence=cfg.min_scoreboard_confidence,
        consensus_reads=2,
    )

    scenes: list[SceneRecord] = []
    confirmed_changes = 0
    valid_reads = 0
    for read in fixture_reads:
        state = _build_scoreboard_state(read)
        if state.parse_valid:
            valid_reads += 1
        change = tracker.update(state)
        if change is None:
            continue
        confirmed_changes += 1
        scenes.append(_change_to_scene(change, cfg))

    sha = submodule_sha() or "unknown"
    return SceneAnalysisResult(
        upload_id=upload_id,
        intel_submodule_sha=sha,
        scenes=scenes,
        raw_metrics={
            "mode": "fixture",
            "fixture_reads": len(fixture_reads),
            "valid_reads": valid_reads,
            "confirmed_changes": confirmed_changes,
            "ocr_backend": "fixture",
            "config_class": type(cfg).__name__,
            "min_scoreboard_confidence": cfg.min_scoreboard_confidence,
        },
    )


def _change_to_scene(change, cfg) -> SceneRecord:
    """Convert OmegaClips ConfirmedScoreChange to AI Director SceneRecord."""
    pre_pad = cfg.pre_event_pad
    post_pad = cfg.post_event_pad
    t_event = float(change.t_confirmed)
    home_before, away_before = change.before
    home_after, away_after = change.after
    return SceneRecord(
        t_start=max(0.0, t_event - pre_pad),
        t_end=t_event + post_pad,
        kind="goal",
        arc_position="climax",
        intensity=float(change.confidence),
        importance=1.0,
        signals={
            "scoreboard_delta": {
                "home_before": home_before,
                "away_before": away_before,
                "home_after": home_after,
                "away_after": away_after,
            },
            "t_detected": change.t_detected,
            "t_confirmed": change.t_confirmed,
            "hold_duration": change.hold_duration,
            "supporting_reads": change.supporting_reads,
            "confirmed_via": "ScoreboardChangeTracker",
            "ocr_confidence": change.confidence,
            "rationale": "score delta confirmed across hold window",
        },
    )


def analyze_video_stub(upload_id: str, source_uri: str) -> SceneAnalysisResult:
    """Legacy stub kept for tests that don't want OmegaClips imports."""
    sha = submodule_sha() or "unknown"
    return SceneAnalysisResult(
        upload_id=upload_id,
        intel_submodule_sha=sha,
        scenes=[
            SceneRecord(
                t_start=0.0,
                t_end=12.0,
                kind="stub_scene",
                signals={"note": "stub adapter; not real OmegaClips output"},
            )
        ],
    )
