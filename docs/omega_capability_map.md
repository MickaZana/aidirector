# OmegaClips Capability Map

**Date:** 2026-05-18
**Submodule pinned at:** `78fcd57` (heads/master) under `packages/intel/`
**Auditor:** AI Director scaffold session
**Method:** read OmegaClips top-level docs (`OMEGACLIPS_PROJECT.md`, `CODEBASE.md`, `CODEBASE_REFERENCE.md`) + targeted grep/read across 491 Python files in `packages/intel/`.

## Status legend

- **A** — exists in OmegaClips today; AI Director integrates via adapter.
- **B** — partial; integrate what's there, build the missing piece behind an interface.
- **C** — not present; AI Director builds it (now, as interface, or defers).
- **UNKNOWN** — couldn't determine in this pass.

## Priority legend

- **P0** — required for the upload→analyze→rank→render→export loop. Phase 0 / Phase 1.
- **P1** — required for the first paying-tenant ship gate. Phase 1.
- **P2** — required for a credible launch. Phase 2.
- **P3** — defer to interface-only or post-launch.

## Feature map (all paths relative to `packages/intel/`)

| # | Feature | Status | OmegaClips evidence | Integration plan | MVP priority |
|---|---|---|---|---|---|
| 1 | Scoreboard OCR | A | `football_pipeline/scoreboard.py::ScoreboardReader`, `football_pipeline/ocr_backends.py`, `football_pipeline/score_ocr.py` | `intel.scene_analysis_adapter` calls reader through orchestrator; AI Director never imports `scoreboard.py` directly | P0 |
| 2 | Clock / game-time detection | A | `football_pipeline/scoreboard.py::CLOCK_PATTERN`, `scoreboard.py::parse_score` | Same adapter as #1; surface parsed clock in `Scene.signals.clock` | P0 |
| 3 | Goal / event confirmation | A | `football_pipeline/goal_windows.py`, `football_pipeline/scoreboard_state_confirmation.py` (FI-8) | Scene rows include `event_kind` derived from FI-8 confirmation output | P0 |
| 4 | Replay detection | A | `football_pipeline/replay_clustering.py`, `football_pipeline/window_ranking.py::compute_shot_change_density` | Replay flags surface on `Scene` as boolean; ranker uses it as a feature | P1 |
| 5 | Crowd reaction detection | B | Reaction signal embedded in FI-3 (`key_moment_detection.py`); no standalone crowd-only detector | Integrate FI-3 reaction signal as-is; defer a dedicated crowd-only detector until labels exist | P1 |
| 6 | Commentator excitement | A | `football_pipeline/audio.py`, `football_pipeline/audio_processing.py`, `key_moment_detection.py::_compute_audio_reaction_signal` | Surface `audio_intensity` and `commentator_spike` on `Scene.signals` | P1 |
| 7 | Celebration detection | B | Reaction signals in FI-3/FI-7; no explicit celebration classifier | Treat as proxy via reaction signal; defer dedicated celebration model | P3 |
| 8 | Referee / VAR moment detection | C | None found | Defer until post-PMF | P3 (defer) |
| 9 | Player-face recognition | B | `actor_tracks.py`, `actor_linking.py` (bbox tracking); `jersey_cues.py` (jersey number) | Track-only today; face recognition deferred | P3 (defer) |
| 10 | Team recognition | B | `roster_context.py`, `jersey_cues.py` (jersey number-based) | Surface team via roster/jersey today; defer crest/colour CV | P3 (defer) |
| 11 | Director — chooses best moments | A | `candidate_clip_selection.py`, `candidate_reel_ranking.py`, `highlight_review_ranker.py` | Adapter wraps ranking output into `RankedClipCandidates` | P0 |
| 12 | Director — clip length / pacing | A | `final_render_plan.py`, `goal_windows.py::clamp_window`, `config.py` clip-length thresholds | Pass platform-target duration caps via `PipelineConfig` overrides | P0 |
| 13 | Director — captions / zooms / overlays | A | `caption_generation.py` (RG-2), `render_composition.py` (RG-1), `dynamic_crop_engine.py`, `caption_variation_engine.py` | Plan emits caption/crop/composition picks; renderer worker executes them | P0 |
| 14 | Director — render style | A | `render_composition.py::COMPOSITION_STRATEGIES` (8), `caption_generation.py::STYLE_LABELS` (5) | Map AI Director platform targets → OmegaClips style label | P1 |
| 15 | Director — multiple variants per clip | A | `caption_variation_engine.py`, `metadata_variants.py`, `distribution_planning.py` | Persist variants under `DirectorPlan.selected_candidates[].variants` | P1 |
| 16 | Director — explains selection | A | `key_moment_detection.py::_build_key_moment_rationale`, `goal_windows.py::GoalCandidateWindow.rationale` | Pass rationale into `Scene.signals.rationale` and `DirectorPlan.reason_selected` | P0 |
| 17 | Scene — breaks match into events | A | `non_goal_events.py`, `event_sequences.py`, `goal_windows.py`, `orchestrator.py` | Adapter persists one `Scene` row per event from orchestrator output | P0 |
| 18 | Scene — emotion / intensity / importance | A | FI-3 → FI-8 layers (`key_moment_detection.py`, `attacking_phase_inference.py`, `decisive_action_inference.py`, `terminal_outcome_typing.py`) | Flatten scores into `Scene.signals` JSONB | P0 |
| 19 | Scene — dead-air detection | B | `audio_processing.py` mute fallback; no dedicated dead-air module | Derive dead-air from low audio intensity; add explicit interface later | P3 |
| 20 | Scene — buildup → climax → reaction tail | A | FI-4 (`attacking_phase_inference`) → FI-5 (`decisive_action_inference`) → FI-7 (`broadcast_payoff_confirmation`) | Persist arc as `Scene.arc_position ∈ {buildup, climax, payoff}` | P1 |
| 21 | Quality score | A | `final_render_plan.py::_compute_render_readiness_score`, render/caption composition scores | Persist as `ClipCandidate.quality_score`; expose as a single 0–1 number on the surface | P1 |
| 22 | Virality score | C | None found | Build behind interface, fill with heuristic v1, learned v2 after data flywheel | P2 (interface now) |
| 23 | Confidence score | A | `ball_aware_candidate_confidence.py` (FI-2) + summary modules | Persist as `ClipCandidate.confidence_score` | P0 |
| 24 | Platform score | B | `metadata_variants.py` has platform tags; no per-platform scoring | AI Director's `services/platform_optimizer.py` computes platform score | P1 |
| 25 | Novelty score | C | None found | Defer | P3 |
| 26 | Duplicate detection | B | `non_goal_events.py` references dedup; no fingerprint-based detector | Window-merge today; full fingerprinting later | P3 |
| 27 | FFmpeg cutting | A | `render_execution.py::execute_render_manifest` (ffmpeg subprocess with `-ss`/`-to`) | Renderer worker is a thin wrapper | P0 |
| 28 | Encoding presets | A | `render_execution.py`, `render_visual_enhancements.py`, `config.py` codec/preset settings | AI Director constructs `PipelineConfig` overrides per platform target | P0 |
| 29 | Audio normalization | A | `audio_processing.py::build_audio_filter` (atrim, aresample, optional loudnorm) | Always on for export; toggle via config | P0 |
| 30 | Watermarking | A | `render_execution.py` drawtext overlay, `billing.py` FREE-tier rule | AI Director sets watermark flag based on tenant plan | P1 |
| 31 | Export compression | A | `render_execution.py`, `final_export_manifest.py`, CRF/bitrate in `config.py` | Per-platform CRF/bitrate via `PipelineConfig` overrides | P1 |
| 32 | Aspect-ratio variants (9:16 / 1:1 / 16:9) | A | `smart_crop.py::_target_aspect_ratio`, `dynamic_crop_engine.py`, `config.py::smart_crop_target_width/height` | One `RenderJob` per variant; aspect set in `RenderJob.settings` | P0 |
| 33 | Auto-crop | A | `smart_crop.py`, `smart_crop_framing.py`, `dynamic_crop_engine.py` | Adapter exposes auto-crop as an interface; OmegaClips is the implementation today | P1 |
| 34 | Captions | A | `caption_generation.py` (RG-2), `caption_render.py`, `caption_timing_and_layout.py` | Adapter exposes captions interface; map AI Director caption style → OmegaClips style label | P0 |
| 35 | Motion templates (HyperFrames) | C | `render_visual_enhancements.py` has visual quality only; no motion graphics | AI Director builds in phase 3 (HyperFrames pipeline) | P3 (defer) |
| 36 | Uploads handling (engine) | A | `orchestrator/upload_pipeline.py::run_upload_pipeline`, `job_store.py`, `io.py` | AI Director owns customer-facing uploads; OmegaClips upload pipeline runs inside the analyzer worker after R2 download | P0 |
| 37 | Jobs CRUD (engine) | A | `job_store.py::JobStore`, `job_state_machine.py`, `job_runner.py` | AI Director's `jobs` table is the customer-facing source of truth; OmegaClips' job store is engine-internal (linked via `Job.omegaclips_job_id`) | P0 |
| 38 | Processing status surface | A | `api_facade_handlers.py`, `ui_view_models.py`, OmegaClips `frontend/` | AI Director builds its own; do not reuse OmegaClips' multi-user-blind status views | P1 |
| 39 | Review clips UI | A | OmegaClips `frontend/src/app/jobs/[jobId]/review/page.tsx` | AI Director builds tenant-scoped review workspace from scratch | P2 |
| 40 | Approve / export action | A | `review_actions.py`, `review_session_actions.py`, `final_decision_audit.py` | Adapter exposes approve/export; AI Director's audit trail is in its own DB | P1 |
| 41 | Regenerate variants | A | `caption_variation_engine.py`, `metadata_variants.py`, `distribution_planning.py` | Adapter exposes a `regenerate_variants(candidate_id, overrides)` method | P2 |
| 42 | Compare versions | B | Review action history exists; no diff UI | Defer | P3 |
| 43 | Credits / usage tracking | A | `billing.py::CREDIT_COSTS`, `billing.py::check_action_allowed` | AI Director's `usage_events` table is canonical; OmegaClips' credit logic is engine-internal only | P1 |
| 44 | Orgs / tenants | C | None found in engine | AI Director builds `tenants` table + tenant_id column on every row | P0 |
| 45 | Roles / RBAC | B | `billing.py::Tier` enum (FREE/CREATOR/PRO/ADMIN), `reviewer_fit_matrix.py` | Tier flags only today; full RBAC deferred | P3 |
| 46 | Billing (Stripe) | B | `billing.py` tiers + EUR pricing; no Stripe integration | AI Director writes `usage_events` now; full Stripe metered billing in Phase 1 | P1 |
| 47 | Hook generator | B | `caption_generation.py` (`_SHOT_HOOKS`, `_CUTBACK_HOOKS`) template-only | AI Director builds generative hook agent behind interface | P2 (interface now) |
| 48 | Engagement predictor | C | None found | Interface now, heuristic v1 in phase 2, learned v2 phase 4 | P2 (interface now) |
| 49 | Platform optimizer | C | `metadata_variants.py` has tags only; no scoring | AI Director's `services/platform_optimizer.py` provides per-platform aspect/duration/bitrate config | P1 |
| 50 | A/B variants | B | Variants generated by OmegaClips; no experiment harness | Interface now, full harness in phase 4 | P2 (interface now) |
| 51 | Queue | B | `job_store.py` + `job_runner.py` (polling, custom) | AI Director uses Redis + RQ on top; OmegaClips JobStore remains the engine-internal state machine (plan §5 Option B) | P0 |
| 52 | GPU workers | C | None in engine | Modal GPU for HyperFrames phase 3 | P3 (defer) |
| 53 | Storage abstraction (R2/S3) | C | Local FS only (`io.py` uses `workspace/`) | AI Director adapter downloads R2 → ephemeral Modal scratch → invokes engine on local paths → uploads outputs back | P0 |
| 54 | Observability (Sentry/Logfire) | C | None found in engine | AI Director wires Sentry + Logfire in `apps/api` and `workers` | P1 |

## Summary

- **A (integrate as-is):** 27 features — 50% of the requested set is already real OmegaClips capability. Adapter contract is what unlocks them.
- **B (partial, integrate + extend):** 13 features — wrap what exists; queue the missing pieces.
- **C (build in AI Director):** 14 features — almost all are SaaS-shell / cloud-orchestration / new pipelines. None are sports intelligence.

**Sports intelligence is 90% there.** The product moat is the integration contract and the SaaS shell around it, not re-implementing CV/OCR.

## Adapter implications

Every A and B feature is reached through one of four adapter calls:

```
analyze_video(upload_id, source_uri) -> SceneAnalysisResult
rank_clip_candidates(upload_id, scenes) -> RankedClipCandidates
create_director_plan(upload_id, ranked, platform_targets) -> DirectorPlan
render_clip_variant(plan_id, candidate_id, settings) -> RenderOutput
```

AI Director code never imports `football_pipeline.*` outside `workers/` and `apps/api/src/api/services/intel/`.
