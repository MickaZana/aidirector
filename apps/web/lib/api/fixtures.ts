/**
 * Offline fixtures matching the real backend Pydantic shapes.
 *
 * Used when the API endpoint isn't reachable yet (Phase 9 ships ahead
 * of the dashboard composite routes — Phase 9.5 wires them). The UI is
 * built against the same types, so swapping fixtures → live API is one
 * provider change.
 *
 * Numbers below mirror the actual probe outputs from Phases 2–8 so the
 * UI reflects realistic shapes (e.g. ranking_engine="OmegaClips.window_ranking",
 * base_rank_score=0.394 + engagement_adjustment=0.096 = final 0.49).
 */
import type {
  ClipCandidate,
  DirectorPlan,
  ExportArtifact,
  Job,
  JobView,
  PerformanceFeatureView,
  RankingSnapshot,
  RenderJob,
  RenderOutput,
  Scene,
  Upload,
  UsageEvent,
} from "./types";

const TENANT_ID = "tenant_demo_01";
const UPLOAD_ID = "01913f78-1b6d-7c92-9a64-1a6b6b50c2f9";
const JOB_ID = "01913f78-2d4f-7c92-9a64-3b1b6b50c2fa";
const SCENE_0_ID = "01913f78-3e5e-7c92-9a64-4c2b6b50c2fb";
const SCENE_1_ID = "01913f78-4f6f-7c92-9a64-5d3b6b50c2fc";
const CAND_0_ID = "01913f78-5071-7c92-9a64-6e4b6b50c2fd";
const CAND_1_ID = "01913f78-6182-7c92-9a64-7f5b6b50c2fe";
const RJ_0_ID = "01913f78-7293-7c92-9a64-8a6b6b50c2ff";
const RO_0_ID = "01913f78-83a4-7c92-9a64-9b7b6b50c300";
const EXPORT_0_ID = "01913f78-94b5-7c92-9a64-ac8b6b50c301";

const ISO = (offsetMin: number) => {
  const d = new Date(Date.now() + offsetMin * 60_000);
  return d.toISOString();
};

const upload: Upload = {
  id: UPLOAD_ID,
  tenant_id: TENANT_ID,
  filename: "barca_vs_real_2026_full.mp4",
  r2_key: `tenant/${TENANT_ID}/upload/${UPLOAD_ID}/barca_vs_real_2026_full.mp4`,
  bytes: 2_138_492_103,
  duration_s: 5_412.0,
  sport: "football",
  status: "ready",
  created_at: ISO(-12),
};

const job: Job = {
  id: JOB_ID,
  tenant_id: TENANT_ID,
  upload_id: UPLOAD_ID,
  intent: "analyze",
  status: "succeeded",
  intel_submodule_sha: "78fcd572e9a3852e2cea73765fd8eda0c304d76d",
  error: null,
  cost_budget_cents: 30,
  cost_actual_cents: 18,
  created_at: ISO(-11),
};

const scenes: Scene[] = [
  {
    id: SCENE_0_ID,
    job_id: JOB_ID,
    tenant_id: TENANT_ID,
    t_start: 14.0,
    t_end: 28.0,
    kind: "goal",
    arc_position: "climax",
    intensity: 0.86,
    importance: 0.95,
    signals: {
      scoreboard_delta: { home_before: 0, away_before: 0, home_after: 1, away_after: 0 },
      confirmed_via: "ScoreboardChangeTracker",
      supporting_reads: 2,
      audio_intensity: 0.88,
      rationale: "scoreboard increment + crowd peak + replay confirm",
    },
  },
  {
    id: SCENE_1_ID,
    job_id: JOB_ID,
    tenant_id: TENANT_ID,
    t_start: 42.0,
    t_end: 56.0,
    kind: "goal",
    arc_position: "climax",
    intensity: 0.84,
    importance: 0.92,
    signals: {
      scoreboard_delta: { home_before: 1, away_before: 0, home_after: 1, away_after: 1 },
      confirmed_via: "ScoreboardChangeTracker",
      supporting_reads: 2,
    },
  },
];

const candidates: ClipCandidate[] = [
  {
    id: CAND_0_ID,
    job_id: JOB_ID,
    tenant_id: TENANT_ID,
    scene_id: SCENE_0_ID,
    t_start: 14.0,
    t_end: 28.0,
    confidence_score: 0.49,        // Phase 8 final (base + engagement_adjustment)
    quality_score: 0.629,
    platform_score: 0.5,
    rationale: "goal_action ranking favored score-context 0.525 and shot-change 0.344",
    scores: {
      rank: 1,
      rank_score: 0.49,
      base_rank_score: 0.394,
      engagement_adjustment: 0.096,
      final_rank_score: 0.49,
      feedback_applied: true,
      feature_version: "v1",
      confidence_threshold: 0.3,
      engagement_weight_cap: 0.15,
      feedback_explanation:
        "Confidence=0.8000 above threshold 0.3; engagement_score=0.9000 centered around 0.5; adjustment upward +0.0960 (cap ±0.15); base 0.3940 → final 0.4900.",
      ranking_engine: "OmegaClips.window_ranking",
      ranking_intent: "goal_action",
    },
  },
  {
    id: CAND_1_ID,
    job_id: JOB_ID,
    tenant_id: TENANT_ID,
    scene_id: SCENE_1_ID,
    t_start: 42.0,
    t_end: 56.0,
    confidence_score: 0.385,
    quality_score: 0.621,
    platform_score: 0.5,
    rationale: "goal_action ranking favored score-context 0.510 and shot-change 0.336",
    scores: {
      rank: 2,
      rank_score: 0.385,
      base_rank_score: 0.385,
      engagement_adjustment: 0.0,
      final_rank_score: 0.385,
      feedback_applied: false,
      feature_version: "n/a",
      confidence_threshold: 0.3,
      engagement_weight_cap: 0.15,
      ranking_engine: "OmegaClips.window_ranking",
      ranking_intent: "goal_action",
    },
  },
];

const directorPlan: DirectorPlan = {
  version: "1",
  upload_id: UPLOAD_ID,
  job_id: JOB_ID,
  model: "deterministic-builder/v1",
  prompt_version: "v1",
  platform_targets: ["youtube_shorts", "tiktok", "instagram_reels"],
  cost_estimate_cents: 18,
  selected_candidates: [
    {
      candidate_id: CAND_0_ID,
      reason_selected:
        "goal + crowd payoff + clear scoreboard; high engagement on prior export",
      confidence_score: 0.49,
      quality_score: 0.629,
      platform_score: 0.5,
      clip_start: 14.0,
      clip_end: 28.0,
      duration: 14.0,
      pacing: "fast",
      caption_style: "sports_hype",
      crop_strategy: "action",
      render_style: "sports_hype",
      hook_options: ["OFF THE BENCH AND IT'S IN", "70 SECONDS AFTER COMING ON"],
      variants: [
        { variant_id: "v1", platform: "youtube_shorts", aspect_ratio: "9:16", duration_cap: 60, caption_safe_zone: true, watermark: true },
        { variant_id: "v2", platform: "tiktok", aspect_ratio: "9:16", duration_cap: 60, caption_safe_zone: true, watermark: true },
        { variant_id: "v3", platform: "instagram_reels", aspect_ratio: "9:16", duration_cap: 90, caption_safe_zone: true, watermark: true },
      ],
    },
    {
      candidate_id: CAND_1_ID,
      reason_selected: "equaliser; goal_action ranking favoured shot-change density",
      confidence_score: 0.385,
      quality_score: 0.621,
      platform_score: 0.5,
      clip_start: 42.0,
      clip_end: 56.0,
      duration: 14.0,
      pacing: "medium",
      caption_style: "sports_hype",
      crop_strategy: "action",
      render_style: "ffmpeg_basic",
      hook_options: [],
      variants: [
        { variant_id: "v1", platform: "youtube_shorts", aspect_ratio: "9:16", duration_cap: 60, caption_safe_zone: true, watermark: true },
        { variant_id: "v2", platform: "tiktok", aspect_ratio: "9:16", duration_cap: 60, caption_safe_zone: true, watermark: true },
        { variant_id: "v3", platform: "instagram_reels", aspect_ratio: "9:16", duration_cap: 90, caption_safe_zone: true, watermark: true },
      ],
    },
  ],
};

const renderJobs: RenderJob[] = [
  {
    id: RJ_0_ID,
    job_id: JOB_ID,
    tenant_id: TENANT_ID,
    candidate_id: CAND_0_ID,
    pipeline: "ffmpeg_basic",
    platform: "youtube_shorts",
    status: "succeeded",
    settings: { aspect_ratio: "9:16", duration_cap: 60, watermark: true },
    error: null,
    finished_at: ISO(-9),
    cost_cents: 2,
    created_at: ISO(-10),
  },
];

const renderOutputs: RenderOutput[] = [
  {
    id: RO_0_ID,
    render_job_id: RJ_0_ID,
    tenant_id: TENANT_ID,
    r2_key: `local://renders/phase9_demo_${CAND_0_ID.slice(0, 8)}_yt_shorts.mp4`,
    aspect_ratio: "9:16",
    duration_s: 14.0,
    bytes: 2_043_077,
    output_metadata: { platform: "youtube_shorts", renderer: "ffmpeg_basic", elapsed_seconds: 1.73 },
  },
];

const exports_: ExportArtifact[] = [
  {
    id: EXPORT_0_ID,
    tenant_id: TENANT_ID,
    render_output_id: RO_0_ID,
    platform: "youtube_shorts",
    export_status: "uploaded",
    export_version: 1,
    export_hash: "4a0688a567c769279a68c7635edc38c65b9ef8cec6e3b18474de5cfd9eff7ca3",
    content_hash: "c6440cd18f9dcec2ca395de003b9f4206dee9c5d954920fdb23076bddc6906c4",
    content_bytes: 2_043_077,
    filename: "phase9_demo_youtube_shorts_v1.mp4",
    storage_uri: `local://exports/phase9_demo_youtube_shorts_v1.mp4`,
    artifact_metadata: { duration_s: 14.0, aspect_ratio: "9:16" },
    published_at: null,
    created_at: ISO(-8),
  },
];

const featureViews: PerformanceFeatureView[] = [
  {
    export_id: EXPORT_0_ID,
    tenant_id: TENANT_ID,
    feature_version: "v1",
    maturity_state: "stable",
    engagement_confidence: 0.8,
    normalized_view_rate: 0.78,
    normalized_completion_rate: 0.62,
    normalized_watch_time: 0.71,
    replay_rate: 0.08,
    share_rate: 0.04,
    engagement_score: 0.9,
    experiment_group_id: null,
  },
];

const snapshots: RankingSnapshot[] = [
  {
    id: "01913f78-a5c6-7c92-9a64-bd9b6b50c302",
    tenant_id: TENANT_ID,
    candidate_id: CAND_0_ID,
    job_id: JOB_ID,
    source_export_id: EXPORT_0_ID,
    base_rank_score: 0.394,
    engagement_adjustment: 0.096,
    final_rank_score: 0.49,
    feature_version: "v1",
    feedback_applied: true,
    confidence_threshold: 0.3,
    engagement_weight_cap: 0.15,
    explanation:
      "Confidence=0.8000 above threshold 0.3; engagement_score=0.9000 centered around 0.5; adjustment upward +0.0960 (cap ±0.15); base 0.3940 → final 0.4900.",
    snapshot_metadata: {
      breakdown: {
        engagement_confidence: 0.8,
        confidence_threshold: 0.3,
        engagement_score: 0.9,
        maturity_state: "stable",
        centered: 0.8,
        scaled_by_confidence: 0.64,
        capped: 0.096,
        engagement_weight_cap: 0.15,
        direction: "upward",
      },
    },
    created_at: ISO(-5),
  },
  {
    id: "01913f78-b6d7-7c92-9a64-cea0c6b50c303",
    tenant_id: TENANT_ID,
    candidate_id: CAND_1_ID,
    job_id: JOB_ID,
    source_export_id: null,
    base_rank_score: 0.385,
    engagement_adjustment: 0.0,
    final_rank_score: 0.385,
    feature_version: "n/a",
    feedback_applied: false,
    confidence_threshold: 0.3,
    engagement_weight_cap: 0.15,
    explanation: "No prior performance view supplied; ranker uses base score only.",
    snapshot_metadata: { breakdown: { reason: "no_feature_view" } },
    created_at: ISO(-5),
  },
];

const usageEvents: UsageEvent[] = [
  { id: "u1", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: null, event_type: "upload_created", quantity: 1, unit: "upload", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-12) },
  { id: "u2", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "analysis_started", quantity: 1, unit: "job", estimated_cost_cents: null, event_metadata: { intent: "analyze" }, created_at: ISO(-11) },
  { id: "u3", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "analysis_completed", quantity: 2, unit: "scene", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-10.5) },
  { id: "u4", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "ranking_started", quantity: 1, unit: "job", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-10.4) },
  { id: "u5", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "candidate_created", quantity: 1, unit: "candidate", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-10.3) },
  { id: "u6", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "ranking_completed", quantity: 2, unit: "ranking", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-10.2) },
  { id: "u7", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "director_plan_created", quantity: 1, unit: "plan", estimated_cost_cents: 18, event_metadata: { candidates: 2, variants: 6 }, created_at: ISO(-10) },
  { id: "u8", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "render_started", quantity: 1, unit: "render", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-9.5) },
  { id: "u9", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "render_completed", quantity: 14, unit: "clip_seconds", estimated_cost_cents: 2, event_metadata: { renderer: "ffmpeg_basic" }, created_at: ISO(-9) },
  { id: "u10", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "export_created", quantity: 1, unit: "export", estimated_cost_cents: null, event_metadata: { platform: "youtube_shorts" }, created_at: ISO(-8) },
  { id: "u11", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "engagement_ingested", quantity: 26, unit: "event", estimated_cost_cents: null, event_metadata: {}, created_at: ISO(-6) },
  { id: "u12", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "evaluation_completed", quantity: 1, unit: "feature_set", estimated_cost_cents: null, event_metadata: { engagement_score: 0.9 }, created_at: ISO(-5) },
  { id: "u13", tenant_id: TENANT_ID, user_id: null, upload_id: UPLOAD_ID, job_id: JOB_ID, event_type: "ranking_feedback_applied", quantity: 2, unit: "snapshot", estimated_cost_cents: null, event_metadata: { feedback_applied: true }, created_at: ISO(-4) },
];

export const FIXTURE_UPLOAD = upload;
export const FIXTURE_JOB = job;
export const FIXTURE_JOB_VIEW: JobView = {
  job,
  upload,
  scenes,
  candidates,
  director_plan: directorPlan,
  render_jobs: renderJobs,
  render_outputs: renderOutputs,
  exports: exports_,
  feature_views: featureViews,
  snapshots,
  usage_events: usageEvents,
};
export const FIXTURE_UPLOADS = [upload];
export const FIXTURE_JOBS = [job];
export const FIXTURE_USAGE_EVENTS = usageEvents;
