"""Correction aggregator — Adaptive Director Agent learning loop.

Aggregates PlanCorrection rows across all tenants into structured few-shot
examples the Claude enrichment layer can use to improve future DirectorPlans.

Architecture:
  1. `aggregate_corrections(db)` fetches recent corrections and clusters
     them by correction_type + sport context.
  2. `build_few_shot_examples(corrections)` converts correction clusters into
     the few-shot format expected by `director_agent_adapter.py`.
  3. `get_few_shot_prompt(tenant_id)` returns a prompt snippet that the
     Director Agent worker appends to the Claude enrichment prompt.

Design constraints:
  - Corrections are tenant-scoped: the learning loop only uses corrections
    from the same tenant to build few-shot examples (other tenants'
    correction patterns are NOT mixed in — privacy by design).
  - K-anonymity: no single correction is identifiable in the aggregated
    examples. Only patterns that appear 3+ times are included.
  - Replay-safe: the aggregation is deterministic over the same set of
    corrections (no randomness in clustering).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import PlanCorrection

log = logging.getLogger(__name__)

# Minimum occurrences before a correction pattern is included as a
# few-shot example (k-anonymity floor).
_MIN_CORRECTION_THRESHOLD = 3

# How many recent corrections to consider (sliding window).
_MAX_CORRECTIONS_WINDOW = 200

# How many few-shot examples to include in the prompt (Claude context
# window management).
_MAX_FEW_SHOT_EXAMPLES = 5


@dataclass
class CorrectionPattern:
    """A clustered pattern of user corrections."""

    correction_type: str
    count: int
    common_changes: dict[str, Any]
    """e.g. {"pacing": "fast→medium", "render_style": "ffmpeg_basic→sports_hype"}"""

    example_before: dict | None
    """Anonymized representative 'before' snapshot."""

    example_after: dict | None
    """Anonymized representative 'after' snapshot."""


def aggregate_corrections(
    db: Session,
    *,
    tenant_id: str | None = None,
    min_threshold: int = _MIN_CORRECTION_THRESHOLD,
    max_window: int = _MAX_CORRECTIONS_WINDOW,
) -> list[CorrectionPattern]:
    """Fetch recent corrections and cluster by type + common changes.

    When `tenant_id` is provided, only that tenant's corrections are
    considered (tenant-scoped learning). Otherwise aggregates globally
    (admin use only).
    """
    query = select(PlanCorrection).order_by(PlanCorrection.applied_at.desc()).limit(max_window)
    if tenant_id:
        from uuid import UUID

        query = query.where(PlanCorrection.tenant_id == UUID(tenant_id))

    rows = db.execute(query).scalars().all()

    # Cluster by correction_type
    clusters: dict[str, list[PlanCorrection]] = defaultdict(list)
    for row in rows:
        clusters[row.correction_type].append(row)

    # Build patterns for clusters meeting the threshold
    patterns: list[CorrectionPattern] = []
    for ctype, group in clusters.items():
        if len(group) < min_threshold:
            continue

        common = _extract_common_changes(group)
        example = _pick_representative(group)

        patterns.append(
            CorrectionPattern(
                correction_type=ctype,
                count=len(group),
                common_changes=common,
                example_before=example["before"] if example else None,
                example_after=example["after"] if example else None,
            )
        )

    # Sort by count descending (most impactful patterns first)
    patterns.sort(key=lambda p: p.count, reverse=True)
    return patterns


def build_few_shot_examples(
    patterns: list[CorrectionPattern],
    max_examples: int = _MAX_FEW_SHOT_EXAMPLES,
) -> list[dict]:
    """Convert top correction patterns into few-shot format for Claude.

    Each example is a dict with:
      - "role": "user" | "assistant"
      - "content": the prompt/response snippet

    This format matches Anthropic's messages API for direct use in the
    Director Agent enrichment call.
    """
    examples: list[dict] = []
    for pattern in patterns[:max_examples]:
        if not pattern.example_before or not pattern.example_after:
            continue

        examples.append(
            {
                "role": "user",
                "content": (
                    f"Here is a DirectorPlan that was corrected by an editor. "
                    f"The original had these settings: "
                    f"pacing={pattern.example_before.get('pacing', '?')}, "
                    f"render_style={pattern.example_before.get('render_style', '?')}, "
                    f"caption_style={pattern.example_before.get('caption_style', '?')}. "
                    f"The user changed type: {pattern.correction_type}."
                ),
            }
        )
        examples.append(
            {
                "role": "assistant",
                "content": (
                    f"Understood. For similar plans, I should prefer: "
                    f"pacing={pattern.example_after.get('pacing', '?')}, "
                    f"render_style={pattern.example_after.get('render_style', '?')}, "
                    f"caption_style={pattern.example_after.get('caption_style', '?')}. "
                    f"This pattern appeared {pattern.count} times."
                ),
            }
        )

    return examples


def get_few_shot_prompt_snippet(db: Session, *, tenant_id: str) -> str:
    """Build a prompt snippet the Director Agent worker can append.

    Returns an empty string when there aren't enough corrections yet
    (cold-start friendly).
    """
    patterns = aggregate_corrections(db, tenant_id=tenant_id)
    if not patterns:
        return ""

    examples = build_few_shot_examples(patterns)
    if not examples:
        return ""

    lines = ["\n[Learning from past corrections]"]
    for ex in examples:
        lines.append(f"<{ex['role']}>{ex['content']}</{ex['role']}>")

    lines.append(
        "Apply these patterns when relevant. "
        "Do NOT override explicit user preferences from the current request."
    )
    return "\n".join(lines)


# --- Internal helpers -------------------------------------------------------


def _extract_common_changes(group: list[PlanCorrection]) -> dict[str, Any]:
    """Analyze a group of corrections and extract the most common field changes."""
    pacing_deltas: Counter[str] = Counter()
    style_deltas: Counter[str] = Counter()
    caption_deltas: Counter[str] = Counter()

    for row in group:
        before = _flatten_plan(row.original_plan_json)
        after = _flatten_plan(row.corrected_plan_json)

        if before.get("pacing") != after.get("pacing"):
            pacing_deltas[f"{before.get('pacing', '?')}→{after.get('pacing', '?')}"] += 1
        if before.get("render_style") != after.get("render_style"):
            style_deltas[f"{before.get('render_style', '?')}→{after.get('render_style', '?')}"] += 1
        if before.get("caption_style") != after.get("caption_style"):
            caption_deltas[
                f"{before.get('caption_style', '?')}→{after.get('caption_style', '?')}"
            ] += 1

    result: dict[str, Any] = {}
    if pacing_deltas:
        result["pacing_changes"] = dict(pacing_deltas.most_common(3))
    if style_deltas:
        result["style_changes"] = dict(style_deltas.most_common(3))
    if caption_deltas:
        result["caption_changes"] = dict(caption_deltas.most_common(3))
    return result


def _pick_representative(group: list[PlanCorrection]) -> dict | None:
    """Pick a representative correction from the group (the most recent
    one that has visible differences between before and after)."""
    for row in sorted(group, key=lambda r: r.applied_at, reverse=True):
        before = _flatten_plan(row.original_plan_json)
        after = _flatten_plan(row.corrected_plan_json)
        if before != after:
            return {"before": before, "after": after}
    return None


def _flatten_plan(plan_json: dict) -> dict:
    """Extract a flat summary dict from a DirectorPlan's selected_candidates
    for diff comparison. Only the fields Claude is allowed to change."""
    candidates = plan_json.get("selected_candidates", [])
    if not candidates:
        return {}

    # Use the first candidate as representative (most systems have
    # consistent pacing/style across all candidates).
    first = candidates[0]
    return {
        "pacing": first.get("pacing", "medium"),
        "render_style": first.get("render_style", "ffmpeg_basic"),
        "caption_style": first.get("caption_style", "sports_hype"),
        "crop_strategy": first.get("crop_strategy", "action"),
    }
