"""Optional Claude enrichment layer for DirectorPlan.

**Sandboxed.** The deterministic builder owns shape, timestamps, variants,
aspect ratios, and pipeline compatibility. Claude is only allowed to rewrite
a small set of *content* fields per candidate. Any suggestion that fails
schema validation, names an unsupported enum value, or tries to modify a
protected field is dropped silently — the original deterministic value
stands.

If `enabled=False` (the default) or `enricher_fn` is None, this is a no-op
identity function: the input plan is returned unchanged. The Phase 4 probe
runs in this mode so the deterministic path is exercised without any LLM
dependency.

When enabled, the caller is responsible for providing an `enricher_fn` that
maps a small request dict → a small response dict. That allows the
Anthropic client / model / API key / prompt caching to live entirely in the
calling code; the adapter has no Anthropic dependency itself.
"""

from __future__ import annotations

from typing import Callable

from api.schemas.director_plan import (
    CaptionStyle,
    DirectorPlan,
    Pacing,
    RenderStyle,
    SelectedCandidate,
)

# Fields Claude may suggest values for. Anything else in its response is
# ignored. This list is intentionally tiny.
WHITELISTED_FIELDS = frozenset(
    {
        "reason_selected",
        "pacing",
        "caption_style",
        "render_style",
        "hook_options",
    }
)

# Valid enum values per whitelisted enum field. Used to reject hallucinated
# strings before they hit Pydantic.
_VALID_PACING: frozenset[Pacing] = frozenset(("fast", "medium", "slow"))
_VALID_CAPTION_STYLE: frozenset[CaptionStyle] = frozenset(("sports_hype", "minimal", "documentary"))
_VALID_RENDER_STYLE: frozenset[RenderStyle] = frozenset(
    ("ffmpeg_basic", "sports_hype", "documentary", "conversation", "static")
)

MAX_HOOK_OPTIONS = 4
MAX_HOOK_LENGTH = 80
MAX_REASON_LENGTH = 280


EnricherFn = Callable[[dict], dict]
"""(request_payload_dict) -> response_payload_dict.

Caller is responsible for wrapping the actual Anthropic call. The adapter
hands the enricher a constrained request describing each candidate, and
expects back a dict keyed by `candidate_id` with optional whitelisted
field suggestions.
"""


def enrich_director_plan(
    plan: DirectorPlan,
    *,
    enabled: bool = False,
    enricher_fn: EnricherFn | None = None,
    model: str = "claude-sonnet-4-6",
    few_shot_examples: list[dict] | None = None,
) -> DirectorPlan:
    """Apply optional, sandboxed enrichment to a deterministic DirectorPlan.

    No-op identity function unless `enabled=True` AND `enricher_fn` is
    provided. Always re-validates the result through Pydantic; if validation
    fails for any reason, the original plan is returned unchanged.

    `few_shot_examples` — optional list of dicts with "role" and "content"
    keys, for appending correction-derived learning patterns to the prompt.
    Passed through from `correction_aggregator.build_few_shot_examples()`.
    """
    if not enabled or enricher_fn is None:
        return plan

    request = _build_enrichment_request(plan, few_shot_examples=few_shot_examples)
    try:
        response = enricher_fn(request)
    except Exception:
        # Any LLM-side failure → fall back to deterministic plan.
        return plan

    enriched = _apply_response(plan, response or {}, model=model)
    try:
        # Final defence: re-validate through Pydantic. If anything is off,
        # discard the enrichment and return the deterministic input.
        return DirectorPlan.model_validate(enriched.model_dump(mode="python"))
    except Exception:
        return plan


# --- Internals --------------------------------------------------------------


def _build_enrichment_request(
    plan: DirectorPlan,
    few_shot_examples: list[dict] | None = None,
) -> dict:
    """Constrained, JSON-shaped request handed to the enricher.

    Only fields Claude needs to do its job are exposed. Timestamps and IDs
    are read-only context (Claude must not modify them — and even if it
    tries, the adapter's apply step refuses).

    `few_shot_examples` — optional learning-loop examples from past user
    corrections, in the format produced by
    `correction_aggregator.build_few_shot_examples()`.
    """
    request: dict = {
        "plan_version": plan.version,
        "upload_id": plan.upload_id,
        "job_id": plan.job_id,
        "platform_targets": list(plan.platform_targets),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "clip_start": c.clip_start,
                "clip_end": c.clip_end,
                "duration": c.duration,
                "confidence_score": c.confidence_score,
                "quality_score": c.quality_score,
                "platform_score": c.platform_score,
                "pacing": c.pacing,
                "caption_style": c.caption_style,
                "render_style": c.render_style,
                "reason_selected": c.reason_selected,
                "hook_options": list(c.hook_options),
            }
            for c in plan.selected_candidates
        ],
        "whitelisted_fields": sorted(WHITELISTED_FIELDS),
        "constraints": {
            "max_hook_options": MAX_HOOK_OPTIONS,
            "max_hook_length": MAX_HOOK_LENGTH,
            "max_reason_length": MAX_REASON_LENGTH,
        },
    }

    if few_shot_examples:
        request["few_shot_examples"] = few_shot_examples
        request["learning_context"] = (
            "The following few-shot examples show how this tenant's editor "
            "has corrected similar plans in the past. Apply these patterns "
            "when relevant, but do NOT override explicit user preferences "
            "from the current request."
        )

    return request


def _apply_response(plan: DirectorPlan, response: dict, *, model: str) -> DirectorPlan:
    """Apply per-candidate suggestions to a deepcopied DirectorPlan.

    Drops anything not whitelisted, anything beyond length limits, and
    anything that doesn't match a known enum value.
    """
    suggestions = response.get("candidates", {}) or {}
    if not isinstance(suggestions, dict):
        return plan

    new_candidates: list[SelectedCandidate] = []
    for cand in plan.selected_candidates:
        per = suggestions.get(cand.candidate_id) or {}
        if not isinstance(per, dict):
            new_candidates.append(cand)
            continue
        new_candidates.append(_apply_per_candidate(cand, per))

    return plan.model_copy(
        update={
            "selected_candidates": new_candidates,
            "model": model,
        }
    )


def _apply_per_candidate(cand: SelectedCandidate, per: dict) -> SelectedCandidate:
    updates: dict = {}

    if "reason_selected" in per and isinstance(per["reason_selected"], str):
        text = per["reason_selected"].strip()
        if 0 < len(text) <= MAX_REASON_LENGTH:
            updates["reason_selected"] = text

    if "pacing" in per and per["pacing"] in _VALID_PACING:
        updates["pacing"] = per["pacing"]

    if "caption_style" in per and per["caption_style"] in _VALID_CAPTION_STYLE:
        updates["caption_style"] = per["caption_style"]

    if "render_style" in per and per["render_style"] in _VALID_RENDER_STYLE:
        updates["render_style"] = per["render_style"]

    hooks = per.get("hook_options")
    if isinstance(hooks, list):
        cleaned = [
            h.strip() for h in hooks if isinstance(h, str) and 0 < len(h.strip()) <= MAX_HOOK_LENGTH
        ]
        if cleaned:
            updates["hook_options"] = cleaned[:MAX_HOOK_OPTIONS]

    if not updates:
        return cand
    return cand.model_copy(update=updates)
