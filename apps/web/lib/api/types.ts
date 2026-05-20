/**
 * Typed API contract — must mirror the backend Pydantic models exactly.
 *
 * Source of truth on the backend:
 *   apps/api/src/api/schemas/director_plan.py
 *   apps/api/src/api/schemas/render_manifest.py
 *   apps/api/src/api/services/intel/capability_registry.py
 *   apps/api/src/api/models/*.py
 *
 * Rules:
 *   - Add a type here BEFORE adding a backend field.
 *   - Never reach into raw event tables (engagement_events) from the
 *     client — only `PerformanceFeatureView` is exposed via the API.
 *   - Drift between this file and Pydantic = a backend bug. The probe
 *     layer doesn't validate the wire shape; the API client does at
 *     parse time (and falls back to fixtures for unknown shapes).
 */

// --- Domain enums ----------------------------------------------------------

export type UploadStatus =
  | "pending"
  | "uploaded"
  | "ingesting"
  | "ready"
  | "failed";

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type RenderJobStatus =
  | "queued"
  | "rendering"
  | "succeeded"
  | "failed";

export type ExportArtifactStatus =
  | "pending"
  | "uploading"
  | "uploaded"
  | "published"
  | "failed";

export type MaturityState = "fresh" | "maturing" | "stable" | "decayed";

export type PlatformTarget =
  | "youtube_shorts"
  | "tiktok"
  | "instagram_reels"
  | "x";

export type AspectRatio = "9:16" | "1:1" | "16:9";

export type RenderStyle =
  | "ffmpeg_basic"
  | "sports_hype"
  | "documentary"
  | "static";

export type CaptionStyle = "sports_hype" | "minimal" | "documentary";

export type CropStrategy = "center" | "action" | "face" | "manual";

export type Pacing = "fast" | "medium" | "slow";

// --- Core rows -------------------------------------------------------------

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  plan: string;
  created_at: string;
}

export interface Upload {
  id: string;
  tenant_id: string;
  filename: string;
  r2_key: string;
  bytes: number | null;
  duration_s: number | null;
  sport: string;
  status: UploadStatus;
  created_at: string;
}

export interface Job {
  id: string;
  tenant_id: string;
  upload_id: string;
  intent: string;
  status: JobStatus;
  intel_submodule_sha: string | null;
  error: string | null;
  cost_budget_cents: number;
  cost_actual_cents: number;
  created_at: string;
}

export interface Scene {
  id: string;
  job_id: string;
  tenant_id: string;
  t_start: number;
  t_end: number;
  kind: string;
  arc_position: string | null;
  intensity: number | null;
  importance: number | null;
  signals: Record<string, unknown>;
}

export interface ClipCandidate {
  id: string;
  job_id: string;
  tenant_id: string;
  scene_id: string | null;
  t_start: number;
  t_end: number;
  confidence_score: number | null;
  quality_score: number | null;
  platform_score: number | null;
  rationale: string | null;
  /**
   * Carries the Phase 8 feedback breakdown when present:
   *   base_rank_score / engagement_adjustment / final_rank_score
   *   feedback_applied / feature_version
   *   confidence_threshold / engagement_weight_cap / feedback_explanation
   *   feedback_breakdown
   *   ranking_intent / ranking_engine / signal_breakdown
   */
  scores: Record<string, unknown>;
}

// --- DirectorPlan contract (editorial intent) -----------------------------

export interface Variant {
  variant_id: string;
  platform: PlatformTarget;
  aspect_ratio: AspectRatio;
  duration_cap: number;
  caption_safe_zone: boolean;
  watermark: boolean;
}

export interface SelectedCandidate {
  candidate_id: string;
  reason_selected: string;
  confidence_score: number;
  quality_score: number;
  platform_score: number;
  clip_start: number;
  clip_end: number;
  duration: number;
  pacing: Pacing;
  caption_style: CaptionStyle;
  crop_strategy: CropStrategy;
  render_style: RenderStyle;
  hook_options: string[];
  variants: Variant[];
}

export interface DirectorPlan {
  version: string;
  upload_id: string;
  job_id: string;
  model: string;
  prompt_version: string;
  platform_targets: PlatformTarget[];
  selected_candidates: SelectedCandidate[];
  cost_estimate_cents: number;
}

// --- Render path (executable intent) --------------------------------------

export interface RenderJob {
  id: string;
  job_id: string;
  tenant_id: string;
  candidate_id: string;
  pipeline: string;
  platform: string;
  status: RenderJobStatus;
  settings: Record<string, unknown>;
  error: string | null;
  finished_at: string | null;
  cost_cents: number | null;
  created_at: string;
}

export interface RenderOutput {
  id: string;
  render_job_id: string;
  tenant_id: string;
  r2_key: string;
  aspect_ratio: AspectRatio;
  duration_s: number | null;
  bytes: number | null;
  output_metadata: Record<string, unknown>;
}

// --- Export identity + telemetry (Phases 6 + 7 + 8) -----------------------

export interface ExportArtifact {
  id: string;
  tenant_id: string;
  render_output_id: string;
  platform: string;
  export_status: ExportArtifactStatus;
  export_version: number;
  export_hash: string;
  content_hash: string;
  content_bytes: number | null;
  filename: string;
  storage_uri: string;
  artifact_metadata: Record<string, unknown>;
  published_at: string | null;
  created_at: string;
}

/**
 * Phase 7 read-only projection. The client surface gets ONLY these 12
 * derived fields — never raw `engagement_events`. Mirrors
 * `apps/api/src/api/services/intel/ranking_feedback_adapter.py::PerformanceFeatureView`.
 */
export interface PerformanceFeatureView {
  export_id: string;
  tenant_id: string;
  feature_version: string;
  maturity_state: MaturityState;
  engagement_confidence: number;
  normalized_view_rate: number | null;
  normalized_completion_rate: number | null;
  normalized_watch_time: number | null;
  replay_rate: number | null;
  share_rate: number | null;
  engagement_score: number;
  experiment_group_id: string | null;
}

/** Phase 8 ranking audit row. */
export interface RankingSnapshot {
  id: string;
  tenant_id: string;
  candidate_id: string;
  job_id: string;
  source_export_id: string | null;
  base_rank_score: number;
  engagement_adjustment: number;
  final_rank_score: number;
  feature_version: string;
  feedback_applied: boolean;
  confidence_threshold: number;
  engagement_weight_cap: number;
  explanation: string;
  snapshot_metadata: Record<string, unknown>;
  created_at: string;
}

// --- Usage events ---------------------------------------------------------

export type UsageEventType =
  | "upload_created"
  | "analysis_started"
  | "analysis_completed"
  | "ranking_started"
  | "ranking_completed"
  | "candidate_created"
  | "director_plan_created"
  | "render_started"
  | "render_completed"
  | "export_created"
  | "engagement_ingested"
  | "evaluation_completed"
  | "ranking_feedback_applied"
  | "credits_reserved"
  | "credits_consumed"
  | "credits_refunded"
  | "job_failed"
  | "user_approved_clip";

export interface UsageEvent {
  id: string;
  tenant_id: string;
  user_id: string | null;
  upload_id: string | null;
  job_id: string | null;
  event_type: UsageEventType;
  quantity: number;
  unit: string;
  estimated_cost_cents: number | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
}

// --- Pipeline view-models (client-only, derived from rows) ----------------

export type PipelineStageKey =
  | "upload"
  | "analysis"
  | "ranking"
  | "directing"
  | "rendering"
  | "exporting"
  | "feedback";

export interface PipelineStage {
  key: PipelineStageKey;
  label: string;
  status: "idle" | "queued" | "running" | "succeeded" | "failed";
  started_at: string | null;
  finished_at: string | null;
  elapsed_seconds: number | null;
  detail: Record<string, unknown> | null;
}

export interface JobView {
  job: Job;
  upload: Upload;
  scenes: Scene[];
  candidates: ClipCandidate[];
  director_plan: DirectorPlan | null;
  render_jobs: RenderJob[];
  render_outputs: RenderOutput[];
  exports: ExportArtifact[];
  feature_views: PerformanceFeatureView[];
  snapshots: RankingSnapshot[];
  usage_events: UsageEvent[];
}

/**
 * Polling status refresh — cheap heartbeat for the JobEventTransport.
 * Mirrors `apps/api/src/api/schemas/job_view.py::JobEventsView`.
 *
 * The client polls this every few seconds. When `revision` (monotonic,
 * bumped on each usage_event row) changes, it refetches the full JobView.
 */
export interface JobEvents {
  job_id: string;
  status: JobStatus;
  revision: number;
  last_event_at: string | null;
  last_event_type: UsageEventType | null;
  counts: {
    scenes: number;
    candidates: number;
    render_jobs: number;
    render_outputs: number;
    exports: number;
    feature_views: number;
    snapshots: number;
    usage_events: number;
  };
}
