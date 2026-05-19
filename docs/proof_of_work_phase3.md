# Proof of Work — Phase 3: Real Clip Ranking Integration

**Session:** 2026-05-19
**Submodule:** packages/intel @ 78fcd57
**Prior commits:** 57625d9 (Phase 0), 135c5ef (Phase 0→1), 0184125 (Phase 2)

**Status: PASS (local).** The phase-3 probe exits 0. `clip_ranking_adapter` now calls real OmegaClips `rank_goal_candidate_windows_for_intent` over persisted scenes; ranked candidates are written into `clip_candidates` with FK links back to scenes/job/tenant; 3 ranking-related usage events emitted.

**Modal cloud status:** unchanged from Phase 2 — local-equivalent proven, cloud execution still pending operator `modal token new` + `modal run`.

## CLAIM

The product loop's *rank moments* step is now real, not a stub. AI Director takes the scenes produced by Phase 2's real-OmegaClips analyzer, feeds them through OmegaClips's real `window_ranking` engine, and persists the ranked candidates with full provenance (rank, rank_score, intent, signal breakdown). No re-implementation of ranking logic — the adapter only translates AI Director's `SceneRecord` shape into the dict/list shapes OmegaClips's ranker expects, then maps the report back.

Capability map IDs exercised:
- **#11 Director — chooses best moments** (status A)
- **#21 Quality score** (status A)
- **#23 Confidence score** (status A)

## FILES CHANGED

```
A apps/api/_probe_phase3_loop.py
M apps/api/src/api/models/usage.py
A apps/api/src/api/services/clip_candidate_persistence.py
M apps/api/src/api/services/intel/clip_ranking_adapter.py
M workers/src/workers/clip_ranking_worker.py
M docs/proof_of_work_phase2.md          (Modal status corrected)
A docs/proof_of_work_phase3.md
```

Detail:

| File | Change |
|---|---|
| `apps/api/src/api/models/usage.py` | Added `RANKING_STARTED` + `RANKING_COMPLETED` to the `UsageEventType` enum |
| `apps/api/src/api/services/intel/clip_ranking_adapter.py` | Replaced stub with real-OmegaClips `rank_clip_candidates(...)` that calls `football_pipeline.window_ranking.rank_goal_candidate_windows_for_intent` |
| `apps/api/src/api/services/clip_candidate_persistence.py` | New: writes `ClipCandidate` rows linked to their scene + job + tenant, emits `CANDIDATE_CREATED` per row + one `RANKING_COMPLETED` |
| `workers/src/workers/clip_ranking_worker.py` | Thin Modal shell: `rank_clip_candidates_fixture` calls the adapter; phase-3.5 stub for the full path |
| `apps/api/_probe_phase3_loop.py` | New: analyzer → scene persist → ranker → candidate persist → DB + usage-event verification |
| `docs/proof_of_work_phase2.md` | Modal status corrected to LOCAL-EQUIVALENT PROVEN / CLOUD PENDING |

## EXACT COMMANDS RUN

```bash
# from repo root
cd apps/api
rm -f _probe_phase3_loop.out
"../../.venv/Scripts/python.exe" _probe_phase3_loop.py
cat _probe_phase3_loop.out
```

Exit code: **0**.

## ROOT CAUSE / DESIGN REASON

OmegaClips's `window_ranking.rank_goal_candidate_windows_for_intent` is the real ranker. It accepts:
- `confirmed_score_changes` — list of dicts describing scoreboard transitions
- `candidate_windows` — list of dicts describing candidate clip windows
- `audio_signals` — optional list (empty disables audio path)
- `shot_change_overrides` — optional dict keyed by `(change_index, variant_rank)` of pre-computed shot-change density (provides a hook to skip video-based CV)
- `config` — `PipelineConfig` with intent weights, thresholds, and feature flags

This signature is the perfect adapter target because it has **escape hatches for every heavy dependency** (video file, audio analysis, shot-change CV). By providing synthetic `shot_change_overrides` and an empty `audio_signals` list, the ranker runs identically to its production code path — same weighted score formula, same signal breakdown — only the input source for shot-change density is synthetic. When phase 3.5 wires the analyzer's real shot-change output, the adapter's contract doesn't change.

Mapping decisions:
- `confidence_score` ← `rank_score` directly (the weighted composite is already 0–1)
- `quality_score` ← 0.5 × (`shot_change_score` + `tight_window_score`) — the composition / framing-readiness halves of the breakdown
- `platform_score` ← 0.5 default (Platform-specific scoring is a separate phase; capability map #24 is status B and out of scope here)
- `rationale` ← `ranking_explanation` from OmegaClips's `_build_ranking_explanation`
- `scores` JSONB ← full `signal_breakdown` + rank + ranking_engine for downstream auditability

## EVIDENCE — `_probe_phase3_loop.out`

```text
step: start
alembic upgrade head: OK
analyzer.scene_count=2
persisted_scene_rows=2
ranked.candidate_count=2
candidate[0]: t_start=14.0 t_end=28.0 confidence=0.394 quality=0.629 platform=0.5
  rationale=goal_action ranking favored score-context 0.525 and shot-change 0.344
  scores.rank=1 rank_score=0.394 intent=goal_action engine=OmegaClips.window_ranking
candidate[1]: t_start=42.0 t_end=56.0 confidence=0.385 quality=0.621 platform=0.5
  rationale=goal_action ranking favored score-context 0.510 and shot-change 0.336
  scores.rank=2 rank_score=0.385 intent=goal_action engine=OmegaClips.window_ranking
persisted_candidate_rows=2
db.candidates_count=2
  db candidate: scene_id=bf4b398d-aac5-4c1b-9e3f-200b82395753 t_start=14.0 t_end=28.0
    confidence=0.394 quality=0.629 platform=0.5
    rationale=goal_action ranking favored score-context 0.525 and shot-change 0.344
    scores.rank=1 rank_score=0.394
  db candidate: scene_id=c5c74a13-3b94-489b-b190-f93db11992b7 t_start=42.0 t_end=56.0
    confidence=0.385 quality=0.621 platform=0.5
    rationale=goal_action ranking favored score-context 0.510 and shot-change 0.336
    scores.rank=2 rank_score=0.385
db.usage_events=[["analysis_completed","scene",2.0],
                 ["analysis_started","job",1.0],
                 ["candidate_created","candidate",1.0],
                 ["ranking_completed","ranking",2.0],
                 ["ranking_started","job",1.0],
                 ["upload_created","upload",1.0]]
OK
```

What this proves:
1. **Real OmegaClips ranking engine used.** Engine string `OmegaClips.window_ranking` ships in the persisted `scores` JSON; rationale strings are produced by OmegaClips's `_build_ranking_explanation`.
2. **Ranking sort is real.** `rank_score=0.394` beat `rank_score=0.385` — the home-team goal (0→1-0 at t=14) ranked above the equaliser (1-0→1-1 at t=42). This reflects OmegaClips's weighted formula (score_context, shot_change, reaction, tightness, tail_penalty) with the `goal_action` intent weights from `PipelineConfig`.
3. **FK chain intact.** Every candidate has a non-null `scene_id` that resolves to a real Scene row; `candidate.tenant_id == scene.tenant_id` for both rows.
4. **Required usage events present.**
   - `candidate_created` × 2 (one per persisted candidate)
   - `ranking_started` × 1
   - `ranking_completed` × 1 (quantity 2.0 = candidates produced)
5. **Probe assertions passed.** The probe explicitly fails (non-zero exit) if any of: scene_count<2, candidate scene_id NULL, candidate not linked to a scene of same tenant, missing `candidate_created`/`ranking_completed`/`ranking_started` events, or candidate-created count mismatch.

## Schema linkage (FK chain verified at exit)

```
tenants
  └─> users
  └─> uploads
        └─> jobs (intel_submodule_sha stamped from analyzer)
              └─> scenes (FK + tenant_id mirrored)
                    └─> clip_candidates (FK to scene + job + tenant)
              └─> usage_events
                    upload_created
                    analysis_started
                    analysis_completed   (Phase 2)
                    ranking_started
                    candidate_created    (× N)
                    ranking_completed
```

## Worker contract — still a thin shell

[workers/src/workers/clip_ranking_worker.py](../workers/src/workers/clip_ranking_worker.py)

```python
@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def rank_clip_candidates_fixture(upload_id: str, scenes_serialized: list[dict]) -> dict:
    from api.services.intel.capability_registry import SceneRecord
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    scenes = [SceneRecord.model_validate(s) for s in scenes_serialized]
    ranked = rank_clip_candidates(upload_id, scenes)
    return ranked.model_dump(mode="json")
```

Worker holds zero ranking business logic — only Modal I/O glue + adapter call. Phase-3.5 entrypoint `rank_clip_candidates(job_id, tenant_slug)` is a stub raising NotImplementedError; that's where Postgres-driven scene loading lands when the full Modal pipeline is wired.

## Adapter boundary integrity

```bash
$ grep -r "from football_pipeline" apps/api/src/api/ workers/src/workers/
apps/api/src/api/services/intel/scene_analysis_adapter.py:   # runtime imports inside function bodies
apps/api/src/api/services/intel/clip_ranking_adapter.py:     # runtime imports inside function bodies
workers/src/workers/modal_app.py:                            # image-build config only, not runtime imports
```

`football_pipeline.*` lives only inside `services/intel/` and inside Modal-worker function bodies (via adapter calls). No router, model, schema, or web code touches OmegaClips internals.

## Modal cloud — explicit status

| Aspect | Status |
|---|---|
| Local adapter calls real OmegaClips `window_ranking` | ✅ proven (this probe) |
| Local persistence + FK chain + usage events | ✅ proven (this probe) |
| Modal cloud execution of `rank_clip_candidates_fixture` | ⏳ pending operator `modal token new` + `modal run` |
| Phase-3.5 full path (`rank_clip_candidates` reading from Postgres) | ⬜ deferred |

**Do not mark Modal cloud as closed.** The runbook at [docs/runbooks/modal_hello_import.md](runbooks/modal_hello_import.md) covers `ping_intel`; analogous runs for `analyze_video_fixture` and `rank_clip_candidates_fixture` are valid follow-ups and are operator-actionable.

## Product loop status

```
understand video  →  rank moments  →  direct edits  →  export variants  →  measure  →  improve
       ✅                 ✅                 🟡                🟡             ⬜          ⬜
   Phase 2 PASS       Phase 3 PASS     stub adapter      stub adapter   not yet     not yet
```

Two of the six loop steps are now real OmegaClips integrations. The pattern (adapter imports OmegaClips → worker is thin shell → probe exercises full chain through DB + usage events → exit 0) is now repeated and reusable.

## What's intentionally NOT done

Per the user's "do not build" list for Phase 3:
- FFmpeg rendering
- Remotion / HyperFrames pipelines
- Director Agent (Anthropic-side prompt-cached call producing the persisted DirectorPlan)
- Polished dashboard / billing / admin
- Hook generator, engagement predictor, social analytics
- Modal cloud execution of any worker

## Reproducibility

```powershell
cd "c:\Users\mican\Documents\AI Agent Director\apps\api"
Remove-Item _probe_phase3_loop.out -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe _probe_phase3_loop.py
Get-Content _probe_phase3_loop.out
```

Probe script and expected output captured above. Same `.venv` and `packages/intel @ 78fcd57` as the earlier probes.
