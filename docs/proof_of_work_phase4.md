# Proof of Work — Phase 4: Deterministic DirectorPlan + Sandboxed Claude Enrichment

**Session:** 2026-05-19
**Submodule:** packages/intel @ 78fcd57
**Prior commits:** 57625d9 (Phase 0), 135c5ef (Phase 0→1), 0184125 (Phase 2), 80528f7 (Phase 3)

**Status: PASS (local).** The phase-4 probe exits 0 across three independent sub-tests: deterministic-only build, valid sandboxed enrichment, and hallucinated enrichment rejection. The deterministic planner is the **authority** for shape, timestamps, variants, aspect ratios, and pipeline compatibility. Claude is wired as an optional layer that may only rewrite a whitelisted set of content fields; everything else is dropped before persistence.

**Modal cloud status:** unchanged. Local-equivalent proven, cloud execution still pending operator auth.

---

## CLAIM

The product loop's *direct edits* step is now real, **without introducing AI-generated schema instability**. The DirectorPlan that gets persisted to `director_plans.plan_json` is always Pydantic-validated, deterministic in shape, and verifiable from a fixture. Claude (when later wired) cannot:

- invent candidates or remove them
- change timestamps, candidate IDs, durations, or platform_targets
- emit unsupported enum values (`pacing`, `caption_style`, `render_style`)
- inject oversized strings
- bypass the Pydantic contract
- generate executable commands

The Phase 4 probe is the test harness that proves all of these.

---

## FILES CHANGED

```
A apps/api/src/api/services/director_plan_builder.py
A apps/api/src/api/services/director_plan_persistence.py
A apps/api/src/api/services/intel/director_agent_adapter.py
A workers/src/workers/director_worker.py
A apps/api/_probe_phase4_loop.py
A docs/proof_of_work_phase4.md
```

| File | Role |
|---|---|
| `services/director_plan_builder.py` | **Authority.** Pure-function builder: ranked candidates → validated `DirectorPlan` with safe defaults and per-platform variants |
| `services/intel/director_agent_adapter.py` | **Sandbox.** Optional enrichment with whitelisted fields + value validation + double Pydantic re-validation before return |
| `services/director_plan_persistence.py` | Writes `director_plans` row + emits `DIRECTOR_PLAN_CREATED` (third Pydantic validation pass for defense-in-depth) |
| `workers/director_worker.py` | Thin Modal shell: `build_director_plan_fixture` calls builder, optionally enricher; phase-4.5 stub for full Postgres-driven path |
| `apps/api/_probe_phase4_loop.py` | Three sub-tests (deterministic, valid enrichment, hallucinated enrichment) |
| `docs/proof_of_work_phase4.md` | This file |

---

## EXACT COMMANDS RUN

```bash
cd "c:/Users/mican/Documents/AI Agent Director/apps/api"
rm -f _probe_phase4_loop.out
"../../.venv/Scripts/python.exe" _probe_phase4_loop.py
cat _probe_phase4_loop.out
```

Exit: **0**.

---

## ROOT CAUSE / DESIGN REASON

User's correction (verbatim): *"You need deterministic DirectorPlan generation FIRST … Claude may rewrite/explain/suggest. Claude must NOT invent arbitrary JSON shape, invent unsupported pipelines, emit raw FFmpeg commands, bypass schema validation, control persistence logic."*

The architecture matches that mandate exactly:

```
ClipCandidate rows
        │  (ORM rows, from Phase 3 ranking)
        ▼
  director_plan_builder.build_director_plan(...)
        │  ← AUTHORITY: shape, timestamps, candidate selection, variants,
        │     aspect ratios, duration caps, default pacing/caption/crop,
        │     stable variant IDs, cost estimate
        ▼
  DirectorPlan (Pydantic-validated on construction)
        │
        ▼  (optional)
  director_agent_adapter.enrich_director_plan(plan, enabled=…, enricher_fn=…)
        │  ← SANDBOX: only the whitelisted fields below may change.
        │     Anything else in Claude's response is silently dropped.
        │     Final result is re-validated through DirectorPlan.model_validate.
        │     If anything fails, the input plan is returned unchanged.
        ▼
  director_plan_persistence.persist_director_plan(...)
        │  ← persists row + emits DIRECTOR_PLAN_CREATED. One more
        │     defensive Pydantic round-trip before INSERT.
        ▼
  director_plans row in DB
```

### Whitelisted fields (the *only* things Claude may touch)

| Field | Constraint applied by the sandbox |
|---|---|
| `reason_selected` | str, length 1–280, else reject |
| `pacing` | must be in `{fast, medium, slow}`, else reject |
| `caption_style` | must be in `{sports_hype, minimal, documentary}`, else reject |
| `render_style` | must be in `{ffmpeg_basic, sports_hype, documentary, static}`, else reject |
| `hook_options` | list[str], each 1–80 chars, max 4 entries; oversized entries dropped |

Everything else — including timestamps, candidate IDs, variants, platform_targets, version, cost_estimate, scoring — is owned by the deterministic builder and stays unchanged across any enrichment attempt.

### Why an enricher_fn callable (not direct Anthropic SDK use)

The adapter has zero `anthropic` import. The caller supplies an `EnricherFn` — a `Callable[[dict], dict]` — which is responsible for wrapping the actual Anthropic API call (with prompt caching, model choice, tool use, retries). This keeps the adapter:

- Test-friendly: probes inject fake enrichers (one valid, one hallucinated) and assert behavior deterministically.
- Provider-agnostic: swapping to Bedrock / Vertex / a local model is a wiring change in the worker, not a rewrite of the boundary.
- Dependency-light: the adapter file works without any LLM SDK installed.

---

## EVIDENCE — `_probe_phase4_loop.out`

```text
step: start
alembic upgrade head: OK
analyzer.scene_count=2
persisted_scene_rows=2
persisted_candidate_rows=2

A.plan.model=deterministic-builder/v1
A.plan.selected_candidates=2
A.plan.platform_targets=['youtube_shorts', 'tiktok', 'instagram_reels']
A.plan.cost_estimate_cents=18
A.candidate[0]: id=45847218-e816-4062-bc60-3a6c3466ef54 clip=14.0->28.0 dur=14.0
  pacing=medium caption=sports_hype crop=action render=ffmpeg_basic
  variants=[('youtube_shorts','9:16',60), ('tiktok','9:16',60), ('instagram_reels','9:16',90)]
A.candidate[1]: id=53b6eb42-7985-474a-8124-fd63e41291a1 clip=42.0->56.0 dur=14.0
  pacing=medium caption=sports_hype crop=action render=ffmpeg_basic
  variants=[('youtube_shorts','9:16',60), ('tiktok','9:16',60), ('instagram_reels','9:16',90)]

B.enriched.model=claude-test-fake
B.candidate[0]: pacing=medium caption=documentary render=sports_hype
  reason='rewritten by valid enricher' hooks=['FIRST HOOK', 'SECOND HOOK']
B.candidate[1]: pacing=medium caption=documentary render=sports_hype
  reason='rewritten by valid enricher' hooks=['FIRST HOOK', 'SECOND HOOK']

C.candidate[0]: pacing=medium caption=sports_hype render=ffmpeg_basic
  hook_count=1 reason_len=69
C.candidate[1]: pacing=medium caption=sports_hype render=ffmpeg_basic
  hook_count=1 reason_len=69

sub-tests A/B/C: OK
db.director_plans_count=1
db.plan.model=deterministic-builder/v1
db.plan.candidate_count=2
db.plan.variant_count=6
recovered.upload_id=b39dd1c7-4bb4-4ca8-a824-8c3dfc5fec34
recovered.job_id=97b3e95e-3145-4e37-a40d-6f64bbb5acdb
recovered.platform_targets=['youtube_shorts', 'tiktok', 'instagram_reels']
db.usage_events=[["analysis_completed","scene",2.0],
                 ["analysis_started","job",1.0],
                 ["candidate_created","candidate",1.0],
                 ["director_plan_created","plan",1.0],
                 ["ranking_completed","ranking",2.0],
                 ["upload_created","upload",1.0]]
OK
```

### Sub-test A — deterministic-only build (exit 0 required by acceptance)

- Plan model = `deterministic-builder/v1` (proves no LLM influence)
- 2 candidates selected from 2 ranked rows
- 3 variants per candidate (6 total)
- Each variant carries platform-correct aspect ratio + duration cap from `PLATFORM_PRESETS`:
  - youtube_shorts → 9:16, 60s
  - tiktok → 9:16, 60s
  - instagram_reels → 9:16, 90s
- `cost_estimate_cents=18` (6 variants × $0.03 placeholder per variant)
- Defaults applied: `pacing=medium`, `caption_style=sports_hype`, `crop=action`, `render_style=ffmpeg_basic`
- `enrich_director_plan(enabled=False)` returns *exactly* the input plan (identity test asserts model_dump equality)

### Sub-test B — valid sandboxed enrichment

Fake `valid_enricher` returns whitelisted suggestions for every candidate:
- `reason_selected` → "rewritten by valid enricher" ✅ applied
- `pacing` → "medium" ✅ applied
- `caption_style` → "documentary" ✅ applied
- `render_style` → "sports_hype" ✅ applied
- `hook_options` → ["FIRST HOOK", "SECOND HOOK"] ✅ applied
- `model` → "claude-test-fake" ✅ applied (top-level model name update)

Protected-field invariant assertions (probe exits 12 on failure):
- `candidate_id` unchanged
- `clip_start` unchanged
- `clip_end` unchanged
- `duration` unchanged

### Sub-test C — hallucinated enrichment rejected (the key sandbox proof)

Fake `evil_enricher` returns garbage:
- `reason_selected = "x" * 9999` (oversized)
- `pacing = "ultra_warp_speed"` (not in enum)
- `caption_style = "neon_skyboard"` (not in enum)
- `render_style = "ai_god_mode"` (not in enum)
- `hook_options = ["ok hook", "x" * 9999]` (mixed valid + oversized)
- Plus injections: `clip_start=0.0`, `clip_end=999.0`, `candidate_id="ATTACKER_OVERRIDE"`, `confidence_score=1.0`
- Plus top-level shape pollution: `evil_extra_field`, `selected_candidates="should be ignored"`

Probe-verified outcomes (each is a separate fail-exit if violated):
- `pacing` stayed at deterministic `medium` (rejected "ultra_warp_speed") — exit 20 if not
- `caption_style` stayed at deterministic `sports_hype` (rejected "neon_skyboard") — exit 21
- `render_style` stayed at deterministic `ffmpeg_basic` (rejected "ai_god_mode") — exit 22
- `reason_selected` length stayed 69 chars (deterministic baseline, oversized rejected) — exit 23
- `hook_options=["ok hook"]` — the one valid 7-char string kept, the oversized one dropped — exit 24
- `candidate_id` / `clip_start` / `clip_end` / `confidence_score` all unchanged from deterministic baseline — exit 25
- Candidate count unchanged (no injection/removal possible) — exit 26

### DB-side verification

- `db.director_plans_count=1` — exactly one persisted plan
- `db.plan.candidate_count=2`, `db.plan.variant_count=6`
- `DirectorPlan.model_validate(plan_row.plan_json)` round-trips clean
- `director_plan_created` usage event present alongside the prior Phase 2/3 events
- Tenant and job linkage intact

---

## Module relationships

```
apps/api/src/api/
├── schemas/director_plan.py         (contract — unchanged in Phase 4)
└── services/
    ├── director_plan_builder.py     (NEW: authority over shape)
    ├── director_plan_persistence.py (NEW: row write + event)
    └── intel/
        └── director_agent_adapter.py(NEW: sandboxed enrichment)

workers/src/workers/
└── director_worker.py               (NEW: thin Modal shell)

apps/api/
└── _probe_phase4_loop.py            (NEW: 3-sub-test probe)
```

The `services/intel/` package now hosts both the OmegaClips adapters (scene_analysis, clip_ranking, render_plan) and the Claude enrichment adapter. The shared theme: *adapter modules are the only places where external systems are called from inside AI Director*. The deterministic core (`builder`, `persistence`, routers, models) never imports Anthropic, FFmpeg, OpenCV, or football_pipeline.

---

## Adapter boundary integrity

```
$ grep -rn "from anthropic\|import anthropic" apps/api/ workers/
(no matches — Claude SDK is never imported anywhere yet, by design)
```

The `EnricherFn = Callable[[dict], dict]` shape means the adapter is provider-agnostic. Wiring real Anthropic is a one-file change in `director_worker.py` later, with the boundary unchanged.

---

## Worker contract — still a thin shell

[workers/src/workers/director_worker.py](../workers/src/workers/director_worker.py)

```python
@app.function(image=intel_image, secrets=secrets, timeout=180, memory=2048)
def build_director_plan_fixture(
    upload_id, job_id, candidate_payloads, platform_targets,
    enable_enrichment=False,
) -> dict:
    namespaced = [SimpleNamespace(**c) for c in candidate_payloads]
    plan = build_director_plan(
        upload_id=upload_id, job_id=job_id,
        candidates=namespaced, platform_targets=platform_targets,
    )
    plan = enrich_director_plan(plan, enabled=enable_enrichment, enricher_fn=None)
    return DirectorPlan.model_validate(plan.model_dump(mode="python")).model_dump(mode="json")
```

12 lines of body. Zero planning logic. The deterministic builder and the sandboxed enricher do all the work.

---

## Modal cloud — explicit status (still unchanged)

| Aspect | Status |
|---|---|
| Local deterministic build + sandbox + persist | ✅ proven (this probe) |
| Modal cloud execution of `build_director_plan_fixture` | ⏳ pending operator `modal token new` + `modal run` |
| Real Anthropic enrichment with API key | ⬜ deferred — pattern is wired but no live LLM call yet |
| Phase 4.5 full Postgres-driven path | ⬜ deferred |

Do not claim Modal cloud is closed. Local-equivalent ≠ cloud-proven, by design.

---

## Acceptance — every Phase 4 criterion mapped to evidence

| Criterion | ✅ | Evidence |
|---|---|---|
| `_probe_phase4_loop.py` exits 0 | ✓ | confirmed |
| DirectorPlan validates against Pydantic schema | ✓ | builder constructs through `DirectorPlan(...)`; adapter re-validates via `model_validate`; persistence re-validates a third time before INSERT |
| ≥1 ranked candidate becomes a selected candidate | ✓ | 2 selected |
| Variants generated for YT Shorts / TikTok / Reels | ✓ | 6 variants, 3 per candidate × 2 candidates, with correct aspect/duration_cap |
| `usage_events` include `director_plan_created` | ✓ | present in DB |
| Claude output is optional and sandboxed | ✓ | sub-test A runs with `enabled=False`; sub-tests B/C exercise the sandbox |
| Deterministic planner works even with Anthropic disabled | ✓ | Anthropic SDK never imported; sub-test A is the proof |
| Worker remains thin shell | ✓ | `build_director_plan_fixture` body = 12 lines, zero planning logic |
| Proof report includes CLAIM / FILES / COMMANDS / ROOT CAUSE / EVIDENCE | ✓ | all 5 sections above |

---

## Product loop status

```
understand video  →  rank moments  →  direct edits  →  export variants  →  measure  →  improve
       ✅                ✅                 ✅                🟡             ⬜          ⬜
   Phase 2 PASS      Phase 3 PASS      Phase 4 PASS    stub adapter   not yet     not yet
```

Three of six loop steps now real. The integration pattern is now proven three times:
1. Real OmegaClips integration via runtime `submodule_path` insert + lazy import
2. Adapter boundary respected (no SaaS-side leakage)
3. Persistence service writes rows + emits usage events in one transaction
4. Probe exercises the full chain with assertions; exit non-zero on any deviation

Phase 4 added one more pattern: **AI-output sandboxing via field whitelisting + value validation + double-Pydantic round-trip**.

---

## What's intentionally NOT done

Per the user's "do not build" list:
- FFmpeg execution (Phase 5)
- auto-crop engine
- polished UI / dashboard
- billing
- social integrations
- engagement predictor / hook generator full implementation
- template marketplace
- Modal cloud execution

The `hook_options` list is now Claude-rewritable but not Claude-generated yet — production wiring sets `enable_enrichment=True` and passes a real Anthropic-backed `enricher_fn`. That's a follow-up, not Phase 4 scope.

---

## Reproducibility

```powershell
cd "c:\Users\mican\Documents\AI Agent Director\apps\api"
Remove-Item _probe_phase4_loop.out -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe _probe_phase4_loop.py
Get-Content _probe_phase4_loop.out
```

Same `.venv` and `packages/intel @ 78fcd57` as the earlier probes. No additional dependencies required.
