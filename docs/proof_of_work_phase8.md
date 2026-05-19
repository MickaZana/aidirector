# Proof of Work — Phase 8: Controlled Ranking Feedback Integration

**Session:** 2026-05-19
**Submodule:** packages/intel @ 78fcd57
**Prior commits:** 57625d9, 135c5ef, 0184125, 80528f7, 0c41614, 321be23, 29dc178, a989e18

**Status: PASS (local).** Phase 8 probe exits 0 across **eight sub-tests** (no-feedback parity, positive adjustment, confidence gate, cap enforcement, snapshot persistence, usage event payload, import discipline, deterministic replay). The improvement loop closes without sacrificing structural ranking dominance.

---

## CLAIM

The final loop step — *measure → improve* — is closed without the failure modes the user predicted (overfitting, clickbait drift, spike domination). The ranker reads only `PerformanceFeatureView`, applies a deterministic, **structurally-bounded** adjustment, and writes an explainable `RankingSnapshot` row for every candidate. OmegaClips's structural `rank_score` is **never overwritten** — it's preserved as `base_rank_score` in the persisted snapshot and audit log, alongside `engagement_adjustment` and `final_rank_score`.

Hard guarantees baked into code:

| Guarantee | Mechanism |
|---|---|
| Engagement-derived influence is capped | `ENGAGEMENT_WEIGHT_CAP = 0.15` — max ±15% of [0,1] |
| Structural ranking signals dominate | `final = base + capped` with cap << structural range |
| Feedback influence is explainable | `FeedbackOutcome.breakdown` + `explanation` + `RankingSnapshot.snapshot_metadata` |
| Low-confidence engagement contributes zero | `CONFIDENCE_THRESHOLD = 0.30` — below this, adjustment is unconditionally 0 |
| Ranker remains deterministic | `apply_feedback_to_rank_score` is a pure function of `(base, view)` |
| Reversible | `base_rank_score` persisted separately; UNIQUE upsert preserves audit history |
| OmegaClips base score never overwritten | Stored in `RankingSnapshot.base_rank_score` and `scores.base_rank_score`; only `scores.rank_score` (legacy key) is updated to the final |

---

## FILES CHANGED

```
A apps/api/src/api/models/ranking.py
M apps/api/src/api/models/__init__.py
M apps/api/src/api/models/usage.py
A apps/api/alembic/versions/20260519_0004_ranking_snapshots.py
M apps/api/src/api/services/intel/ranking_feedback_adapter.py
M apps/api/src/api/services/intel/clip_ranking_adapter.py
A apps/api/src/api/services/ranking_snapshot_persistence.py
A workers/src/workers/ranking_feedback_worker.py
A apps/api/_probe_phase8_loop.py
A docs/proof_of_work_phase8.md
```

| File | Role |
|---|---|
| `models/ranking.py` | `RankingSnapshot` ORM model. 15 columns + 4 indexes (UNIQUE on `candidate_id, feature_version`). |
| `models/usage.py` | Added `RANKING_FEEDBACK_APPLIED` (now 18 enum members). |
| `alembic/versions/20260519_0004_ranking_snapshots.py` | CREATE TABLE + 4 indexes; reversible. |
| `services/intel/ranking_feedback_adapter.py` | Promoted: added `FeedbackOutcome` dataclass + `apply_feedback_to_rank_score(base, view) → FeedbackOutcome` + constants (`ENGAGEMENT_WEIGHT_CAP=0.15`, `CONFIDENCE_THRESHOLD=0.30`, `NEUTRAL_ENGAGEMENT_MIDPOINT=0.5`). Pure function; same inputs → same outputs. |
| `services/intel/clip_ranking_adapter.py` | Accepts optional `prior_performance: dict[int, PerformanceFeatureView]`. For each ranked candidate, calls `apply_feedback_to_rank_score` and records `base_rank_score`, `engagement_adjustment`, `final_rank_score`, `feedback_applied`, `feature_version`, `confidence_threshold`, `engagement_weight_cap`, `feedback_explanation`, `feedback_breakdown` in the `scores` dict. NEVER imports `EngagementEvent` or `engagement_aggregation`. |
| `services/ranking_snapshot_persistence.py` | Upserts `RankingSnapshot` keyed on (candidate_id, feature_version); emits `RANKING_FEEDBACK_APPLIED` with 9 metadata keys per snapshot. |
| `workers/ranking_feedback_worker.py` | Thin Modal shell. Loads candidates + scenes from DB, hydrates `PerformanceFeatureView`s from a serialised dict, calls the ranker with `prior_performance`, persists snapshots. ~80 lines, zero feedback math. |
| `_probe_phase8_loop.py` | 8 sub-tests A–H. |

---

## EXACT COMMANDS RUN

```bash
cd "c:/Users/mican/Documents/AI Agent Director/apps/api"
rm -f _probe_phase8_loop.out
"../../.venv/Scripts/python.exe" _probe_phase8_loop.py
cat _probe_phase8_loop.out
```

Exit: **0**.

---

## ROOT CAUSE / DESIGN REASON

User's correction (verbatim): *"DO NOT let engagement become a direct additive multiplier, dominant over structural quality, more important than actual football intelligence. The ranking system must remain sports-first, engagement-assisted. NOT engagement-first, sports-second. Otherwise the system optimizes outrage, cheap hooks, chaos, replay bait instead of actual quality."*

The architecture implements that exactly.

### The math (explicit on purpose)

```
view is None  →  adjustment = 0
view.engagement_confidence < CONFIDENCE_THRESHOLD (0.30)  →  adjustment = 0
otherwise:
    centered = (engagement_score - 0.5) * 2          ∈ [-1, +1]
    scaled   = centered * confidence                  ∈ [-1, +1]
    capped   = clamp(±ENGAGEMENT_WEIGHT_CAP,
                     scaled * ENGAGEMENT_WEIGHT_CAP)  ∈ [-0.15, +0.15]
    adjustment = capped
final_rank_score = clamp(0, 1, base + adjustment)
```

- **Structural dominance**: max |adjustment| is 15% of the [0,1] range. A clip with `base_rank_score=0.394` (real OmegaClips ranker output) can move to at most 0.544 (positive cap) or 0.244 (negative cap). Structural signals from the FI-1→FI-13 layers always make up the bulk of the score.
- **Confidence gating**: below 0.30 confidence — i.e. fresh OR low-sample — the engagement contribution is exactly zero. The Phase 7 evaluator's confidence model already down-weights fresh data; this is the second hard gate on top of that.
- **Determinism**: `apply_feedback_to_rank_score` has no clock, no RNG, no DB access. Same (base, view) → byte-identical outcome on every call.
- **Explainability**: `FeedbackOutcome.explanation` produces a human-readable line; `FeedbackOutcome.breakdown` carries every intermediate (`centered`, `scaled_by_confidence`, `capped`, `direction`).
- **Reversibility**: `RankingSnapshot` persists `base_rank_score` separately so toggling feedback off — or reverting `ENGAGEMENT_WEIGHT_CAP` to 0 — is a re-run of the ranker, not a data migration. The UNIQUE upsert on `(candidate_id, feature_version)` keeps the snapshot's identity stable across re-runs.

### Import discipline (Phase 8 hard rule)

Phase 7 mandated *the ranker reads PerformanceFeatureView only*. Phase 8 wires that read. The probe's sub-test G greps the adapter source for forbidden imports:

```
forbidden_patterns = [
    "^\s*from\s+api\.services\.engagement_aggregation",
    "^\s*from\s+api\.models\s+import\s+[^#\n]*EngagementEvent",
    "^\s*import\s+api\.services\.engagement_aggregation",
]
```

`G.violations=[]` is the proof.

---

## EVIDENCE — `_probe_phase8_loop.out`

### Sub-test A — no `prior_performance` → identical Phase 3 behaviour

```
phase8.constants: CONFIDENCE_THRESHOLD=0.3
phase8.constants: ENGAGEMENT_WEIGHT_CAP=0.15

A.ranked_count=2
A.candidate scene=0 base=0.394 adjustment=0.0 final=0.394 feedback_applied=False
A.candidate scene=1 base=0.385 adjustment=0.0 final=0.385 feedback_applied=False
A.baseline_finals=[0.394, 0.385]
```

Without `prior_performance`, the ranker behaves exactly like Phase 3: `base = final`, `adjustment = 0`, `feedback_applied = False`. Backwards-compatible, no surprise regressions.

### Sub-test B — high-confidence positive view → upward adjustment, scoped to scene 0

```
B.scene0 base=0.394 adj=0.096 final=0.49 applied=True
B.scene1 base=0.385 adj=0.0   final=0.385
```

Scene 0 had a `PerformanceFeatureView(engagement_score=0.9, confidence=0.8, maturity=STABLE)` in `prior_performance`. The math:

```
centered = (0.9 - 0.5) * 2 = 0.8
scaled   = 0.8 * 0.8       = 0.64
capped   = 0.64 * 0.15     = 0.096      ← under cap, used as-is
final    = 0.394 + 0.096   = 0.49
```

Scene 1 had no prior view → adjustment 0, untouched. Adjustment respects the cap (|0.096| < 0.15).

### Sub-test C — low confidence → zero (the spike-resistance gate)

```
C.outcome adj=0.0 applied=False
   explanation=Engagement confidence 0.1000 below threshold 0.3; no adjustment.…
```

`confidence=0.10` is below the 0.30 threshold. The function short-circuits to `adjustment=0` and emits a human-readable explanation. **An engagement_score of 0.95 had zero effect** because the confidence was too low. This is the exact protection against ranking on fresh-spike data.

### Sub-test D — cap enforcement at extremes

```
D.max_pos adj=0.15  final=0.65
D.max_neg adj=-0.15 final=0.35
```

- Max positive view (`engagement_score=1.0`, `confidence=1.0`): adjustment lands at exactly **+0.15** = `ENGAGEMENT_WEIGHT_CAP`. Final from 0.5 base is 0.65.
- Max negative view (`engagement_score=0.0`, `confidence=1.0`): adjustment lands at exactly **-0.15**. Final from 0.5 base is 0.35.

Engagement cannot move the score outside the [base-0.15, base+0.15] band. Structural ranking always determines the majority of the value.

### Sub-test E — RankingSnapshot persistence + idempotent upsert

```
E.snapshots_persisted=2
E.snapshot candidate_id=6636dd11-… base=0.394 adj=0.096 final=0.49  feedback_applied=True  feature_version=v1
E.snapshot candidate_id=2e540889-… base=0.385 adj=0.0   final=0.385 feedback_applied=False feature_version=n/a
E.snapshots_after_replay=2
```

Two snapshots persisted (one per ranked candidate). Re-running `persist_ranking_snapshot` with identical inputs does NOT produce duplicates — the UNIQUE (candidate_id, feature_version) constraint + the upsert logic keeps the row count at 2.

### Sub-test F — RANKING_FEEDBACK_APPLIED usage events

```
F.usage_events=[…,["ranking_feedback_applied","snapshot"],…]
F.ranking_feedback_applied.count=4
F.metadata_keys=['base_rank_score','candidate_id','confidence_threshold',
                 'engagement_adjustment','engagement_weight_cap','feature_version',
                 'feedback_applied','final_rank_score','source_export_id']
```

Each `persist_ranking_snapshot` call emitted one event (4 total — 2 initial inserts + 2 upserts on replay). Metadata carries all 9 audit keys including the active threshold + cap values at the moment of the run — so future ranker-weight changes are debuggable against historical snapshots.

### Sub-test G — import discipline (the architectural firewall)

```
G.adapter_src_path=…\clip_ranking_adapter.py
G.violations=[]
```

The probe greps `clip_ranking_adapter.py` source for forbidden imports. **Zero violations.** The ranker reads `PerformanceFeatureView` (and `FeedbackOutcome`) only; it has no path to raw `engagement_events` rows, `engagement_aggregation` rollups, or `EngagementEvent` model imports.

### Sub-test H — deterministic replay

```
H.triples_1=[(0, 0.394, 0.096, 0.49), (1, 0.385, 0.0, 0.385)]
H.triples_2=[(0, 0.394, 0.096, 0.49), (1, 0.385, 0.0, 0.385)]
```

Two back-to-back invocations of the ranker with the same scenes + same `prior_performance` map produce **byte-identical** `(scene_index, base, adjustment, final)` triples for every candidate. The ranker is replayable for regression testing, A/B experiment auditing, and rollback validation.

---

## Bug caught during validation

| # | Bug | Surfaced by | Fix |
|---|---|---|---|
| 13 | Probe assumed `ClipCandidate` ORM rows had a `scene_index` attribute (they only have `scene_id`) | Sub-test E AttributeError on first run | Build `by_scene_index` by zipping `ranked_no_fb.candidates` (Pydantic records, which DO have `scene_index`) with `candidate_rows` (ORM, persisted 1:1 in order) — they're in lock-step because `persist_clip_candidates` iterates the ranked list |

Probe-fixture bug, not architectural. The persistence service was correct; the probe's index mapping wasn't.

---

## Schema state (15 application tables)

```
tenants
  └─> users
  └─> uploads
        └─> jobs
              └─> scenes
                    └─> clip_candidates
                          └─> ranking_snapshots   ← NEW Phase 8
                              UNIQUE(candidate_id, feature_version)
                              FK to clip_candidates + jobs + exports (optional)
              └─> director_plans
              └─> render_jobs
                    └─> render_outputs
                          └─> exports
                                └─> engagement_events
                                └─> performance_feature_sets
        └─> usage_events
experiment_groups
```

`UsageEventType` enum: **18 members; 13 emitted live** in the probe chain (Phase 8 adds `ranking_feedback_applied`).

---

## Worker stays a thin shell

[workers/src/workers/ranking_feedback_worker.py](../workers/src/workers/ranking_feedback_worker.py)

```python
@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def apply_ranking_feedback_fixture(job_id, prior_performance_serialised) -> dict:
    with Session(engine) as db:
        job = db.execute(select(Job).where(...)).scalar_one()
        scene_rows = …
        candidate_rows = …
        prior = {int(k): PerformanceFeatureView(**payload) for k, payload in …}
        ranked = rank_clip_candidates(..., prior_performance=prior)
        for cand_record, target in zip(ranked.candidates, candidate_rows):
            persist_ranking_snapshot(db, job=job, candidate=target, scores=cand_record.scores)
        db.commit()
        return {…}
```

~80 lines, zero math, zero policy. The cap, the threshold, the explanation, the snapshot upsert all live in services. The worker only deserialises views and dispatches.

---

## Acceptance — every Phase 8 criterion mapped to evidence

| Criterion | ✅ | Evidence |
|---|---|---|
| `_probe_phase8_loop.py` exits 0 | ✓ | confirmed |
| Structural score remains visible separately | ✓ | `scores.base_rank_score` persisted alongside `final_rank_score`; `RankingSnapshot.base_rank_score` column |
| Engagement adjustment visible separately | ✓ | `scores.engagement_adjustment` + `RankingSnapshot.engagement_adjustment` |
| Final score deterministic | ✓ | sub-test H: byte-identical triples across replays |
| Ranking snapshots persist correctly | ✓ | sub-test E: 2 snapshots; idempotent upsert preserves count |
| Feedback influence capped correctly | ✓ | sub-test D: extreme inputs land exactly at ±0.15 |
| Confidence gate works | ✓ | sub-test C: confidence=0.10 → adjustment=0 even with engagement_score=0.95 |
| Worker remains thin shell | ✓ | ranking_feedback_worker.py ~80 lines, zero feedback math |
| Proof report CLAIM/FILES/COMMANDS/ROOT-CAUSE/EVIDENCE | ✓ | all 5 sections present |

Plus:
- sub-test A: no-feedback path identical to Phase 3 (regression check)
- sub-test G: zero forbidden imports — architectural firewall verified

---

## Modal cloud — explicit status (still unchanged)

| Aspect | Status |
|---|---|
| Local controlled-feedback ranker | ✅ proven (this probe) |
| Modal cloud execution of `apply_ranking_feedback_fixture` | ⏳ pending operator `modal token new` |
| Phase 8.5 — DB-driven PerformanceFeatureView lookup by scene fingerprint | ⬜ deferred |
| Real connectors that *produce* the `PerformanceFeatureView`s for prior content | ⬜ deferred |

The boundary is clean: any future ingestion path (YouTube Data API, TikTok analytics, manual import) writes to `engagement_events` → evaluation layer → `performance_feature_sets` → `PerformanceFeatureView`. The ranker doesn't know or care where the view came from.

---

## Architectural pattern catalog (now 9 patterns)

1. OmegaClips integration via runtime `submodule_path` insert (Phases 2, 3)
2. Adapter boundary enforcement
3. Persistence-service-per-phase
4. Thin Modal worker shell
5. AI-output sandboxing (Phase 4)
6. Two-layer execution contract (Phase 5)
7. Canonical distributable identity (Phase 6)
8. Gradient-of-trust pipeline (Phase 7)
9. **Capped explainable feedback** (Phase 8) — derived signals enter ranking through a pure function with declared cap + confidence gate + snapshot audit trail; structural signals always dominate

The reusable shape is now: "raw → aggregate → evaluate → derive → read-only view → CAPPED pure-function adjustment → snapshot for audit". Any future reinforcement-learning signal (engagement, watch-time, click-through) plugs in at the "derive" layer; the cap and gate at the "adjustment" layer protect downstream behaviour.

---

## Product loop status

```
understand video  →  rank moments  →  direct edits  →  export variants  →  measure  →  improve
       ✅                ✅                ✅                 ✅              ✅         ✅
   Phase 2 PASS      Phase 3 PASS      Phase 4 PASS      Phase 5 PASS   Phase 6+7  Phase 8 PASS
                                                                          PASS
```

**The full data-flywheel loop is now closed.** Sports intelligence → ranking → directing → rendering → export identity → engagement → trust gradient → controlled feedback → ranking. The flywheel compounds with every export, and the architecture protects against the failure modes (reward hacking, clickbait drift, fresh-spike domination, ranker poisoning).

---

## What's intentionally NOT done

Per the user's "do not build" list for Phase 8:
- ML training pipelines
- Engagement predictor
- Auto-posting
- Recommendation systems
- Reinforcement learning
- Analytics UI
- Autonomous optimization
- Modal cloud execution of any worker
- Real platform-API engagement connectors
- Phase 8.5 DB-driven prior_performance lookup

---

## Reproducibility

```powershell
cd "c:\Users\mican\Documents\AI Agent Director\apps\api"
Remove-Item _probe_phase8_loop.out -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe _probe_phase8_loop.py
Get-Content _probe_phase8_loop.out
```

Same `.venv` and `packages/intel @ 78fcd57` as the earlier probes. First run generates the 30-second test source under `_probe_phase8_fixtures/`.
