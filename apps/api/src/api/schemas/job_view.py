"""JobView — the composite job-page contract.

A single endpoint shape that bundles every row touched by one analysis
Job: upload + job + scenes + clip_candidates + director_plan +
render_jobs + render_outputs + exports + performance_feature_sets +
ranking_snapshots + usage_events.

Wire shape **must** exactly mirror `apps/web/lib/api/types.ts::JobView`.
If you change a field here, change the TypeScript interface in the same
commit. The frontend type-system is the only thing that proves the
contract day-to-day — drift here is a backend bug.

Rules of engagement:
  - This schema is READ-ONLY. There is no JobView write endpoint.
  - Field names match Pydantic-on-the-wire (snake_case), not Python
    attribute access on the ORM model.
  - Datetimes are serialised as ISO 8601 strings (UTC, with offset).
  - UUIDs are serialised as strings (no curly braces).
  - `feature_views` is the trust-gradient projection only — raw
    `engagement_events` rows are deliberately NOT included.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.director_plan import DirectorPlan as DirectorPlanContract


# --- row shapes (one per ORM table that the JobView surfaces) -------------


class UploadView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    filename: str
    r2_key: str
    bytes: int | None
    duration_s: float | None
    sport: str
    status: str
    created_at: str


class JobRowView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    upload_id: str
    intent: str
    status: str
    intel_submodule_sha: str | None
    error: str | None
    cost_budget_cents: int
    cost_actual_cents: int
    created_at: str


class SceneView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str
    tenant_id: str
    t_start: float
    t_end: float
    kind: str
    arc_position: str | None
    intensity: float | None
    importance: float | None
    signals: dict[str, Any] = Field(default_factory=dict)


class ClipCandidateView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str
    tenant_id: str
    scene_id: str | None
    t_start: float
    t_end: float
    confidence_score: float | None
    quality_score: float | None
    platform_score: float | None
    rationale: str | None
    scores: dict[str, Any] = Field(default_factory=dict)


class RenderJobView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    job_id: str
    tenant_id: str
    candidate_id: str
    pipeline: str
    platform: str
    status: str
    settings: dict[str, Any] = Field(default_factory=dict)
    error: str | None
    finished_at: str | None
    cost_cents: int | None
    created_at: str


class RenderOutputView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    render_job_id: str
    tenant_id: str
    r2_key: str
    aspect_ratio: str
    duration_s: float | None
    bytes: int | None
    output_metadata: dict[str, Any] = Field(default_factory=dict)


class ExportArtifactView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    render_output_id: str
    platform: str
    export_status: str
    export_version: int
    export_hash: str
    content_hash: str
    content_bytes: int | None
    filename: str
    storage_uri: str
    artifact_metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: str | None
    created_at: str


class PerformanceFeatureViewRow(BaseModel):
    """Phase 7 read-only projection — 12 derived fields, no raw events."""

    model_config = ConfigDict(extra="forbid")

    export_id: str
    tenant_id: str
    feature_version: str
    maturity_state: Literal["fresh", "maturing", "stable", "decayed"]
    engagement_confidence: float
    normalized_view_rate: float | None
    normalized_completion_rate: float | None
    normalized_watch_time: float | None
    replay_rate: float | None
    share_rate: float | None
    engagement_score: float
    experiment_group_id: str | None


class RankingSnapshotView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    candidate_id: str
    job_id: str
    source_export_id: str | None
    base_rank_score: float
    engagement_adjustment: float
    final_rank_score: float
    feature_version: str
    feedback_applied: bool
    confidence_threshold: float
    engagement_weight_cap: float
    explanation: str
    snapshot_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class UsageEventView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tenant_id: str
    user_id: str | None
    upload_id: str | None
    job_id: str | None
    event_type: str
    quantity: float
    unit: str
    estimated_cost_cents: int | None
    event_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


# --- composite ------------------------------------------------------------


class JobView(BaseModel):
    """Everything one job touches, in one response."""

    model_config = ConfigDict(extra="forbid")

    job: JobRowView
    upload: UploadView
    scenes: list[SceneView] = Field(default_factory=list)
    candidates: list[ClipCandidateView] = Field(default_factory=list)
    director_plan: DirectorPlanContract | None = None
    render_jobs: list[RenderJobView] = Field(default_factory=list)
    render_outputs: list[RenderOutputView] = Field(default_factory=list)
    exports: list[ExportArtifactView] = Field(default_factory=list)
    feature_views: list[PerformanceFeatureViewRow] = Field(default_factory=list)
    snapshots: list[RankingSnapshotView] = Field(default_factory=list)
    usage_events: list[UsageEventView] = Field(default_factory=list)


class JobEventsView(BaseModel):
    """Polling-backed status refresh for one job.

    Cheap to compute (only counts + the latest usage_event timestamp).
    The frontend polls this every ~4s while a job is in flight; when
    `revision` or `last_event_at` changes, the client refetches the full
    JobView. This keeps the heavy composite endpoint off the polling
    hot path.
    """

    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: str
    revision: int  # monotonic, bumped on each usage_event for this job
    last_event_at: str | None
    last_event_type: str | None
    counts: dict[str, int]  # {scenes, candidates, render_jobs, render_outputs, exports, snapshots, feature_views, usage_events}
