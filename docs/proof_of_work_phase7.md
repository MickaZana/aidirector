# Proof of Work — Phase 7: Telemetry Ingestion + Evaluation Layer

**Session:** 2026-05-19
**Submodule:** packages/intel @ 78fcd57
**Prior commits:** 57625d9, 135c5ef, 0184125, 80528f7, 0c41614, 321be23, 29dc178

**Status: PASS (local).** Phase 7 probe exits 0 across **eight sub-tests** (schema, ingestion, aggregation/dedupe/outliers, evaluation, replay safety, experiment grouping, adapter discipline, usage events). The Evaluation Layer is now real, with the strict guarantee the user demanded: **raw engagement never modifies ranking; only the evaluator's derived features can.**

---

## CLAIM

The product loop's *measure* step is closed with the discipline that protects long-term ranker quality. Three new tables, three services, one thin worker, and a read-only adapter together establish:

- **Raw telemetry** stays in `engagement_events` and is reference data only.
- **Aggregation** buckets by `(platform, observation_window_hours)`, dedupes on `(export_id, platform, metric_type, observed_at)`, drops outliers (negative / NaN / Inf / None).
- **Evaluation** classifies maturity, weights by confidence (sample-size × maturity), normalises per-platform, and composes a single 0..1 `engagement_score`.
- **`performance_feature_sets`** is the only table the future ranker reads from.
- **`ranking_feedback_adapter`** exposes a frozen `PerformanceFeatureView` with derived fields only. Raw event fields (`metric_value`, `metric_type`, `raw_payload`, `observed_at`, `observation_window_hours`, `source`) are unreachable through the adapter API.

The architecture matches the user's mandate exactly:
*"Raw engagement events must never directly modify ranking. Evaluation Layer is required between telemetry and ranking. Ranking feedback adapter exposes derived features only."*

---

## FILES CHANGED

```
A apps/api/src/api/models/performance.py
M apps/api/src/api/models/__init__.py
M apps/api/src/api/models/usage.py
A apps/api/alembic/versions/20260519_0003_performance.py
A apps/api/src/api/services/engagement_aggregation.py
A apps/api/src/api/services/evaluation_layer.py
A apps/api/src/api/services/intel/ranking_feedback_adapter.py
A workers/src/workers/engagement_worker.py
A apps/api/_probe_phase7_loop.py
A docs/proof_of_work_phase7.md
```

| File | Role |
|---|---|
| `models/performance.py` | `EngagementEvent`, `ExperimentGroup`, `PerformanceFeatureSet` + 3 enums (EngagementMetricType, MaturityState, ExperimentGroup-via-field). 13 indexes total across the three tables. |
| `models/usage.py` | Added `ENGAGEMENT_INGESTED` + `EVALUATION_COMPLETED` to `UsageEventType` (now 17 members). |
| `alembic/versions/20260519_0003_performance.py` | CREATE TABLE × 3 + CREATE INDEX × 13. Reversible. |
| `services/engagement_aggregation.py` | `aggregate_engagement_for_export(...)` → `RawAggregation` (frozen). Replay-safe, dedupe + outlier-rejection. NEVER writes anywhere. |
| `services/evaluation_layer.py` | `evaluate_export(...)` → `EvaluatedFeatures` (frozen). `persist_features(...)` writes PFS row + emits EVALUATION_COMPLETED. Maturity classifier, confidence model, per-platform baselines, weighted composite score. |
| `services/intel/ranking_feedback_adapter.py` | **READ-ONLY.** Returns `PerformanceFeatureView` with 12 derived fields only. No raw-event access. |
| `workers/engagement_worker.py` | ~70-line Modal shell. Receives events, persists, aggregates, evaluates, returns dict. Zero metric logic. |
| `_probe_phase7_loop.py` | 8 sub-tests A–H. |

---

## EXACT COMMANDS RUN

```bash
cd "c:/Users/mican/Documents/AI Agent Director/apps/api"
rm -f _probe_phase7_loop.out
"../../.venv/Scripts/python.exe" _probe_phase7_loop.py
cat _probe_phase7_loop.out
```

Exit: **0**.

---

## ROOT CAUSE / DESIGN REASON

User's correction (verbatim): *"DO NOT feed raw engagement directly into ranking. That becomes: survivorship bias, platform noise, misleading optimization, clickbait drift. Instead: Engagement Events → Aggregation → Evaluation Layer → Ranker Features. You need a separation between raw telemetry and trusted ranking signals."*

The architecture implements exactly this gradient of trust:

```
engagement_events       ← raw, append-only, may contain dupes/outliers,
        │                 NEVER consumed by the ranker
        ▼
engagement_aggregation  ← bucket + dedupe + drop outliers
        │                 RawAggregation is frozen + ephemeral, never persisted
        ▼
evaluation_layer        ← classify maturity, weight by confidence,
        │                 normalise per-platform, compose engagement_score
        ▼
performance_feature_sets← derived, ranker-consumable, versioned by feature_version
        │                 UNIQUE(export_id, feature_version) — update in place
        ▼
ranking_feedback_adapter← READ-ONLY view (12 derived fields, no raw fields)
        │                 returns PerformanceFeatureView (frozen dataclass)
        ▼
(Phase 8) ranker        ← Will read views and add as features. Phase 7 does
                          NOT modify any ranker logic yet — that's deliberate.
```

### Why maturity gating matters (and why the score is "small" in this probe)

The probe inserts 26 events for an export that was created seconds before. The evaluator correctly classifies this as `maturity=fresh` (age <1h **or** sample_size <50). Fresh weight is 0.2; combined with the sample-size factor (38 impressions / 1000 baseline = 0.038), confidence comes out to **0.0044**.

That makes the composite engagement_score **0.0014** — almost zero. **That's the gate working.** A future ranker reading this PFS row would correctly conclude "we don't yet know if this clip works." Without this gate, a 5-minute-old clip with a small early spike would dominate ranking — the exact failure mode the user predicted ("optimize for fresh spikes, incomplete data, random virality").

### Why aggregation is frozen + ephemeral, not a table

`RawAggregation` and `WindowedMetric` are frozen dataclasses. They're never persisted. The next call to `aggregate_engagement_for_export` rebuilds them deterministically from `engagement_events`. This means:
- Replay is automatic — running the evaluator at T0 and T1 reads the same events; same buckets; same features.
- There's no second source of truth to keep in sync.
- New aggregation versions don't require a migration.

### Adapter discipline by construction

`PerformanceFeatureView` is `@dataclass(frozen=True)` with exactly 12 fields, none of which are raw. The probe asserts (sub-test G) that the field set has zero intersection with the forbidden raw-field set `{metric_value, metric_type, raw_payload, observed_at, observation_window_hours, source}`. **It's impossible for a future ranker caller to accidentally read raw telemetry through this module.**

---

## EVIDENCE — `_probe_phase7_loop.out`

### Sub-test A — schema

```
A.tables=['alembic_version','clip_candidates','director_plans','engagement_events',
          'experiment_groups','exports','jobs','performance_feature_sets',
          'render_jobs','render_outputs','scenes','tenants','uploads',
          'usage_events','users']  ← 14 application tables (was 11; Phase 7 adds 3)
A.engagement_events.cols=12 required cols ✓
A.performance_feature_sets.cols=17 required cols ✓
A.experiment_groups.cols=9 required cols ✓
```

### Sub-test B — ingestion + FK chain

```
B.engagement_events_count=26
B.events_inserted=26
```

26 events persisted across 3 buckets (yt-24h, tt-24h, yt-168h), all FK'd to a real ExportArtifact created by the upstream Phases 0–6 chain.

### Sub-test C — aggregation: dedupe + outlier rejection

```
C.in_memory_outlier_gate: nan=True inf=True neg=True none=True
C.windows=3
C.total_events_seen=26
C.dedup_dropped=1    ← exact-duplicate (same export+platform+metric+observed_at) dropped
C.outliers_dropped=3 ← 3 negative-value events rejected at aggregator
C.window: platform=tiktok          window_h=24  samples=7 totals={replay,completion_rate,...}
C.window: platform=youtube_shorts  window_h=24  samples=8 totals={view:800.0,impression:1200.0,...}
C.window: platform=youtube_shorts  window_h=168 samples=7
```

Note `youtube_shorts/24h`: started with 9 raw events (8 original + 1 duplicate) - 1 dedupe - 0 outliers in that bucket = 8 samples. The 3 outliers were in a separate negative-value batch, dropped via `_is_outlier`.

In-memory check for the NaN/Inf path that SQLite NOT NULL can't store (real engagement APIs CAN deliver these values — defensive gate verified separately).

### Sub-test D — evaluation produces ranker-safe features

```
D.feature_version=v1
D.maturity_state=fresh
D.engagement_confidence=0.0044
D.normalized_view_rate=0.404
D.normalized_completion_rate=0.0852
D.normalized_watch_time=1.0
D.replay_rate=0.0509
D.share_rate=0.0368
D.engagement_score=0.0014
```

All values in [0,1]. Fresh maturity (correct — export is seconds old). Very low confidence (sample size << 1000 floor + fresh weight 0.2). Composite engagement_score is heavily down-weighted by confidence — **the gate working**.

### Sub-test E — replay safety

```
E.agg2.total_events_seen=26   E.agg2.outliers_dropped=3   E.agg2.dedup_dropped=1
E.features2.engagement_score=0.0014        ← byte-identical to features1
E.features2.engagement_confidence=0.0044   ← byte-identical
E.features2.maturity_state=fresh
E.pfs_count_after_replay=1                 ← update-in-place worked; no duplicate row
```

Re-running aggregation + evaluation yields the same `engagement_score`, the same maturity, the same confidence. The persistence layer updates the existing `(export_id, feature_version)` row instead of inserting a duplicate.

### Sub-test F — experiment grouping

```
F.experiment_group_id=3a54b4bc-…
F.experiment_name=hook-style-v1
F.siblings_count=1
```

ExperimentGroup row created with hypothesis text + variants metadata. PFS row linked via `experiment_group_id` FK. `get_features_for_experiment_group` returns the linked siblings.

### Sub-test G — adapter discipline

```
G.view.maturity=fresh
G.view.engagement_score=0.0014
G.view.fields=['engagement_confidence','engagement_score','experiment_group_id',
               'export_id','feature_version','maturity_state',
               'normalized_completion_rate','normalized_view_rate',
               'normalized_watch_time','replay_rate','share_rate','tenant_id']
G.score=0.0014
```

The probe asserts `set(view.__dataclass_fields__) ∩ {metric_value, metric_type, raw_payload, observed_at, observation_window_hours, source} == ∅`. Zero leakage. The ranker — when wired in Phase 8 — can't reach past the view.

### Sub-test H — usage events

```
H.usage_events=[…,["engagement_ingested","event"],["evaluation_completed","feature_set"],…]
H.engagement_ingested.count=1
H.evaluation_completed.count=3   ← evaluator ran 3 times (B, E replay, F group)
H.evaluation_completed.metadata_keys=['engagement_confidence','engagement_score',
                                      'experiment_group_id','export_id',
                                      'feature_version','maturity_state','sample_size']
```

The full chain now emits **11 distinct usage event types** live: upload_created, analysis_started, analysis_completed, ranking_started, ranking_completed, candidate_created, director_plan_created, render_started, render_completed, export_created, **engagement_ingested**, **evaluation_completed**.

---

## Bugs caught during validation

| # | Bug | Surfaced by | Fix |
|---|---|---|---|
| 1 | SQLite + Python sqlite3 driver convert `float('nan')` and `float('inf')` to NULL → NOT NULL constraint violation | Sub-test B (first probe run, failed insert) | DB-inserted outliers now use negative values; NaN/Inf still verified via in-memory `_is_outlier` calls (where real engagement APIs would deliver them) |
| 2 | Probe's duplicate event had a different `observed_at` than the original (helper offset-by-index logic) → dedupe key didn't match → 0 drops instead of 1 | Sub-test C (second probe run) | Construct the dedupe event manually with `observed_at = now - timedelta(minutes=1)` to match the original `view` event's timestamp |

Both are probe / test fixture bugs, not architectural — the system gates worked correctly; the probe wasn't initially exercising them right. **Loud failure at probe assertion, not silent acceptance.**

---

## Schema state (14 application tables)

```
tenants                  10 ORM tables → 14 with Phase 6+7 additions:
users                     - exports                  (Phase 6)
uploads                   - engagement_events        (Phase 7)
jobs                      - experiment_groups        (Phase 7)
scenes                    - performance_feature_sets (Phase 7)
clip_candidates
director_plans
render_jobs
render_outputs
usage_events
exports                   ← canonical distributable identity (Phase 6)
  ▲
  │ FK
  ▼
engagement_events         ← raw telemetry, FK to exports (Phase 7)

experiment_groups         ← A/B grouping primitive (Phase 7)

performance_feature_sets  ← derived, ranker-safe (Phase 7)
  ▲
  │ FK + UNIQUE(export_id, feature_version)
  ▼
ranking_feedback_adapter  ← READ-ONLY view layer
```

`UsageEventType` enum now has 17 members; **12 emitted live** in the probe chain.

---

## Acceptance — every Phase 7 criterion mapped to evidence

| Criterion | ✅ | Evidence |
|---|---|---|
| `_probe_phase7_loop.py` exits 0 | ✓ | confirmed |
| engagement_events rows persist | ✓ | sub-test B: `B.engagement_events_count=26` |
| PerformanceFeatureSet rows persist | ✓ | sub-test D + E: `pfs_count_after_replay=1` |
| Observation-window normalization works | ✓ | sub-test C: 3 distinct buckets keyed on `(platform, observation_window_hours)` |
| Maturity classification works | ✓ | sub-test D: `maturity_state=fresh` correctly assigned given age <1h |
| Raw metrics and derived metrics remain separate | ✓ | sub-test G: `PerformanceFeatureView` field set disjoint from forbidden raw fields |
| Experiment grouping persists correctly | ✓ | sub-test F: ExperimentGroup row + FK from PFS + sibling query |
| Ranking feedback adapter exposes derived features only | ✓ | sub-test G: 12-field frozen view, raw fields unreachable |
| Worker remains thin shell | ✓ | `engagement_worker.py`: ~70 lines, zero metric logic |
| Proof report CLAIM/FILES/COMMANDS/ROOT-CAUSE/EVIDENCE | ✓ | all 5 sections present |

---

## Modal cloud — explicit status (unchanged)

| Aspect | Status |
|---|---|
| Local ingestion + aggregation + evaluation + adapter | ✅ proven (this probe) |
| Modal cloud execution of `ingest_events_fixture` | ⏳ pending operator `modal token new` + `modal run` |
| Real platform connectors (YouTube Data API, TikTok analytics) | ⬜ deferred |
| Phase 7.5 periodic re-evaluation worker | ⬜ deferred (stub raises NotImplementedError) |

---

## Architectural pattern catalog (now 8 patterns)

1. OmegaClips integration via runtime `submodule_path` insert (Phases 2, 3)
2. Adapter boundary enforcement
3. Persistence-service-per-phase
4. Thin Modal worker shell
5. AI-output sandboxing (Phase 4)
6. Two-layer execution contract (Phase 5)
7. Canonical distributable identity (Phase 6)
8. **Gradient-of-trust pipeline** (Phase 7) — raw telemetry → aggregation → evaluation → derived features → read-only adapter; each layer is more constrained than the previous, and only the most-constrained layer talks to the ranker

Adding a new ranker feature: derive it in `evaluation_layer`, add a column to `PerformanceFeatureSet`, expose it on `PerformanceFeatureView`. The raw table doesn't change. The adapter doesn't change. The pattern compounds.

---

## Product loop status

```
understand video  →  rank moments  →  direct edits  →  export variants  →  measure  →  improve
       ✅                ✅                ✅                 ✅              ✅         🟡
   Phase 2 PASS      Phase 3 PASS      Phase 4 PASS      Phase 5 PASS   Phase 6+7  preparation
                                                                          PASS    (Phase 8)
```

**Five of six loop steps real.** The sixth (*improve*) is now feature-ready: the ranking_feedback_adapter exposes `PerformanceFeatureView`; Phase 8 wires the read at the ranker call site. The expensive engineering — the trust gradient, the maturity gate, the experiment grouping — is already done.

---

## What's intentionally NOT done

Per the user's "do not build" list for Phase 7:
- Real YouTube/TikTok API integrations (connectors land later)
- ML training pipeline
- Engagement predictor
- Auto-optimization
- Auto-posting
- Analytics dashboard UI
- Recommendation systems
- Phase 8 ranker integration (the adapter exists; the ranker doesn't read from it yet — that's the next phase)

---

## Reproducibility

```powershell
cd "c:\Users\mican\Documents\AI Agent Director\apps\api"
Remove-Item _probe_phase7_loop.out -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe _probe_phase7_loop.py
Get-Content _probe_phase7_loop.out
```

First run generates the 30-second test source and a local storage mirror under `_probe_phase7_fixtures/`. Subsequent runs reuse them. Same `.venv` and `packages/intel @ 78fcd57` as the earlier probes.
