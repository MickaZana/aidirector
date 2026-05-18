"""OmegaClips integration boundary.

NO module outside this package and `workers/` should import `football_pipeline.*`.

Public surface:
- `omega_client` — submodule SHA + capability registry probe.
- `capability_registry` — the four contracts AI Director calls.
- `scene_analysis_adapter` — wraps OmegaClips orchestrator for scene output.
- `clip_ranking_adapter` — wraps candidate selection + ranking.
- `render_plan_adapter` — translates DirectorPlan SelectedCandidate.render_style
  into the concrete OmegaClips render pipeline call.
"""
from api.services.intel.capability_registry import (
    AnalyzeVideoFn,
    CreateDirectorPlanFn,
    DirectorPlanRequest,
    RankClipCandidatesFn,
    RankedClipCandidates,
    RenderClipVariantFn,
    SceneAnalysisResult,
)

__all__ = [
    "AnalyzeVideoFn",
    "RankClipCandidatesFn",
    "CreateDirectorPlanFn",
    "RenderClipVariantFn",
    "SceneAnalysisResult",
    "RankedClipCandidates",
    "DirectorPlanRequest",
]
