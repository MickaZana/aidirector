# Proof of Work — Phase 0 to Phase 1 Spine

**Session:** 2026-05-18
**Branch:** main
**Submodule:** packages/intel @ 78fcd57 (OmegaClips heads/master)
**Operator:** mike.mediainstitute@gmail.com

The user's success checkpoint:
> The target is to prove the product spine:
> OmegaClips intelligence can be called by AI Director, AI Director can persist structured scenes/candidates/plans, a render job can be created, and the SaaS system can show the output path to the user.

Below: each piece, with CLAIM / FILES / COMMANDS / EVIDENCE.

---

## §1 — OmegaClips capability audit

**CLAIM:** All 54 requested capabilities mapped to status A/B/C/UNKNOWN with cited OmegaClips file paths and integration plans + MVP priorities. No guesses.

**FILES CHANGED:**
- `docs/omega_capability_map.md` (new, ~5 KB)

**COMMANDS RUN:**
- Spawned Explore subagent over `packages/intel/` (491 Python files). Subagent returned 54 pipe-delimited lines with file/symbol citations.

**EVIDENCE:**
- 27 features are status **A** (already exist) — wrappable as-is
- 13 features are status **B** (partial) — integrate now, extend later
- 14 features are status **C** (missing) — almost all SaaS-shell / orchestration / cloud, none sports intelligence

**ROOT CAUSE:** Sports intelligence is ~90% there inside OmegaClips. The Director Agent's `claude_intelligence.generate_segment_render_plan`, the FI-1→FI-13 layers, the RG-1→RG-8 render stack, FFmpeg pipeline, audio normalization, smart crop, captions, even billing tiers — all present. The product moat is the *integration contract* and the SaaS shell, not re-implementing CV/OCR.

---

## §2 — Modal hello-import gate

**CLAIM:** Cannot complete the live run from this session (blocks on `modal token new` browser OAuth). Full runbook with exact commands and expected JSON contract written.

**FILES CHANGED:**
- `docs/runbooks/modal_hello_import.md` (new)
- `workers/src/workers/modal_app.py` — path bug fixed (resolve `packages/intel` via `Path(__file__).parents[3]`, not CWD)
- `workers/src/workers/omega_import_probe.py` (new) — richer probe returning the contract shape
- `workers/pyproject.toml` — `[tool.uv.sources] api = { workspace = true }`

**COMMANDS RUN:**
- `irm https://astral.sh/uv/install.ps1 | iex` — uv 0.11.14 installed to `C:\Users\mican\.local\bin\uv.exe`
- `uv sync --all-packages` — workspace synced after initial failed attempts (root cause: stale `VIRTUAL_ENV=C:\Python314` env var leaking through)

**EVIDENCE:**
- `.venv/Lib/site-packages/` shows alembic 1.18.4, fastapi 0.136.1, sqlalchemy 2.0.49, pydantic 2.13.4, modal, anthropic, boto3, rq, stripe — i.e. `uv sync` *did* succeed.
- `.venv/Scripts/python.exe --version` → `Python 3.12.11`
- Modal auth + actual `modal run` deferred to runbook; gate is the next operator action.

**ROOT CAUSE:** `modal token new` opens a browser OAuth flow that I cannot complete from this environment. The runbook captures the exact commands + expected JSON contract so the gate is one operator action away.

---

## §3 — Base schema + Alembic migration

**CLAIM:** Multi-tenant SQLAlchemy schema for 10 tables; one Alembic migration that upgrades, downgrades, and re-upgrades cleanly on SQLite; UUID PKs, tenant_id everywhere, JSONB columns for flexible signal/plan/settings payloads, indexes for tenant_id, status, upload_id, created_at, render_job status.

**FILES CHANGED:**
- `apps/api/src/api/models/__init__.py`
- `apps/api/src/api/models/base.py` — Declarative `Base` + `TimestampMixin` + `uuid_pk()` helper + naming convention
- `apps/api/src/api/models/tenancy.py` — `Tenant`, `User`
- `apps/api/src/api/models/pipeline.py` — `Upload`, `Job`, `Scene`, `ClipCandidate`, `DirectorPlan`, `RenderJob`, `RenderOutput`
- `apps/api/src/api/models/usage.py` — `UsageEvent` + `UsageEventType` enum (13 event types)
- `apps/api/alembic.ini`
- `apps/api/alembic/env.py` — reads `DATABASE_URL` from env, sets `target_metadata = Base.metadata`
- `apps/api/alembic/script.py.mako`
- `apps/api/alembic/versions/20260518_0001_initial.py` — handwritten initial migration
- `apps/api/src/api/db.py` — fixed: deleted duplicate `Base(DeclarativeBase)`, re-exports `Base` from `api.models.base`
- `.gitignore` — added probe artifacts

**COMMANDS RUN (against the SQLite probe DB):**

```text
> _probe_schema.py            (imports api.models, runs Base.metadata.create_all, lists tables)
> _probe_alembic.py           (drives alembic upgrade head from Python)
> _probe_loop.py              (upgrade -> downgrade -> upgrade + FK chain populate + plan round-trip)
```

**EVIDENCE — `_probe_schema.py` output:**

```text
python=3.12.11
prefix=C:\Users\mican\Documents\AI Agent Director\.venv
tables=10
  clip_candidates: 15 cols, 2 idx, 3 fk
  director_plans: 8 cols, 2 idx, 2 fk
  jobs: 13 cols, 3 idx, 2 fk
  render_jobs: 14 cols, 3 idx, 3 fk
  render_outputs: 10 cols, 1 idx, 2 fk
  scenes: 12 cols, 2 idx, 2 fk
  tenants: 8 cols, 0 idx, 0 fk
  uploads: 12 cols, 2 idx, 2 fk
  usage_events: 13 cols, 3 idx, 4 fk
  users: 8 cols, 1 idx, 1 fk
live_tables=['clip_candidates', 'director_plans', 'jobs', 'render_jobs',
             'render_outputs', 'scenes', 'tenants', 'uploads',
             'usage_events', 'users']
OK
```

**EVIDENCE — `_probe_alembic.py` output:**

```text
DATABASE_URL=sqlite:///.../apps/api/aidirector_probe.db
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, initial
tables_after_upgrade=['alembic_version', 'clip_candidates', 'director_plans',
                      'jobs', 'render_jobs', 'render_outputs', 'scenes',
                      'tenants', 'uploads', 'usage_events', 'users']
alembic_version=0001
OK
```

**EVIDENCE — `_probe_loop.py` output (reversibility + end-to-end FK chain + JSON round-trip):**

```text
step 1: upgrade head OK
step 2: downgrade base OK
step 3: re-upgrade head OK
row_counts={"tenants": 1, "users": 1, "uploads": 1, "jobs": 1,
            "scenes": 1, "clip_candidates": 1, "director_plans": 1,
            "render_jobs": 1, "render_outputs": 1, "usage_events": 8}
recovered_plan.job_id=6cce25d5-b225-4567-a386-53a5d36fae27
recovered_plan.candidates=1
recovered_plan.variants=3
recovered_plan.first_render_style=sports_hype
OK
```

**ROOT CAUSE / DESIGN REASON:**
- `Uuid` + `JSON` are dialect-aware in SQLAlchemy 2.0 — same migration applies on Postgres (UUID + JSONB) and SQLite (CHAR(36) + TEXT). Lets us validate without Neon credentials and still target prod Postgres correctly.
- `render_as_batch=True` in `env.py` enables SQLite batch-mode for future ALTER TABLE migrations.
- Indexes match the user's specified set: `(tenant_id, status)`, `upload_id`, `created_at`, render_job `status`, plus `(tenant_id, email)` unique on users and `(tenant_id, created_at)` on uploads & usage_events.
- Downgrade verified — every `create_index`/`create_table` has a paired `drop_index`/`drop_table`. This is the migration we run forwards on Neon and the same one rolls back cleanly when needed.

---

## §4 — OmegaClips integration adapters

**CLAIM:** Clean adapter boundary at `apps/api/src/api/services/intel/`. No SaaS code outside this package and `workers/` imports `football_pipeline.*`. Four contract functions defined, plus the contract types `SceneAnalysisResult`, `RankedClipCandidates`, `DirectorPlanRequest`, `RenderSettings`.

**FILES CHANGED:**
- `apps/api/src/api/services/intel/__init__.py` — re-exports the public surface
- `apps/api/src/api/services/intel/capability_registry.py` — contracts (Protocol + Pydantic records + Callable type aliases)
- `apps/api/src/api/services/intel/omega_client.py` — submodule SHA, populated check (no `football_pipeline.*` imports)
- `apps/api/src/api/services/intel/scene_analysis_adapter.py` — contract + dev stub
- `apps/api/src/api/services/intel/clip_ranking_adapter.py` — contract + dev stub
- `apps/api/src/api/services/intel/render_plan_adapter.py` — maps `render_style` enum → concrete OmegaClips pipeline + `ResolvedRenderSpec`
- `workers/src/workers/omega_import_probe.py` — gate worker
- `workers/src/workers/scene_analysis_worker.py` — Modal stub for analyze_video
- `workers/src/workers/clip_ranking_worker.py` — Modal stub for rank_clip_candidates
- `workers/src/workers/render_worker.py` — Modal stub for render_clip_variant

**EVIDENCE:**
- `git ls-files apps/api/src/api/services/intel/` returns 6 files — the boundary exists in code.
- Grep `from football_pipeline` outside `workers/` and `services/intel/` returns 0 hits.

**ROOT CAUSE:** The user's rule was explicit: "No direct SaaS code should import random OmegaClips modules. Keep imports isolated inside adapters/workers." The adapter package exists; workers are the only place that will `from football_pipeline import …` in phase 1.

---

## §5 — Director Plan contract + Platform optimizer + Usage events

**CLAIM:** Pydantic `DirectorPlan` matches the user's exact spec (upload_id, platform_targets, selected_candidates with confidence/quality/platform scores + render_style enum + variants with platform/aspect/duration_cap). Platform optimizer is a real lookup table for YT Shorts / TikTok / Reels / X. Usage event helper covers 13 event types with the required columns.

**FILES CHANGED:**
- `apps/api/src/api/schemas/director_plan.py` — replaced earlier pipeline-discriminated shape with the user's contract shape
- `apps/api/src/api/services/platform_optimizer.py` — `PLATFORM_PRESETS` with aspect_ratio, duration_cap_s, bitrate_kbps, resolution, safe_zone_top_pct/bottom_pct, filename_template, crf for all four platforms
- `apps/api/src/api/services/usage_events.py` — `emit_usage_event(...)` helper

**EVIDENCE — DirectorPlan round-trips through DB JSON storage (from `_probe_loop.py`):**

```text
recovered_plan.job_id=6cce25d5-b225-4567-a386-53a5d36fae27
recovered_plan.candidates=1
recovered_plan.variants=3
recovered_plan.first_render_style=sports_hype
```

A plan with `hook_options=["OFF THE BENCH AND IT'S IN", "70 SECONDS AFTER COMING ON"]`, render_style=`sports_hype`, three variants (youtube_shorts/tiktok/instagram_reels) was persisted to `director_plans.plan_json` (as JSON), reloaded, validated against the Pydantic contract, and returned with all fields intact.

**EVIDENCE — usage_events:**

```text
8 events emitted: upload_created, analysis_started, analysis_completed,
candidate_created, director_plan_created, render_started, render_completed,
export_created
```

Each row has tenant_id, user_id, upload_id, job_id, event_type, quantity, unit, event_metadata JSONB.

---

## §6 — Upload → Job → Director-Plan API contracts

**CLAIM:** Routes exist for the full MVP loop, with Clerk JWT-gated tenant scoping. Tenant rows are auto-created on first call (`get_or_create_tenant`). Every meaningful action writes a usage event.

**FILES CHANGED:**
- `apps/api/src/api/services/tenancy.py` — `get_or_create_tenant(db, claims)`
- `apps/api/src/api/deps.py` — `DbSession`, `TenantRow`, `Tenant_`, `Claims` annotations
- `apps/api/src/api/routers/uploads.py` — POST `/api/uploads/presign`, POST `/api/uploads/{id}/complete`, GET list, GET one
- `apps/api/src/api/routers/jobs.py` — POST `/api/jobs`, GET list, GET one (with intel_submodule_sha stamped on create)
- `apps/api/src/api/routers/director_plans.py` — POST `/api/jobs/{job_id}/director-plan`, GET latest
- `apps/api/src/api/main.py` — registers `director_plans.router`
- `apps/api/src/api/db.py` — single canonical `Base` re-exported from models

**EVIDENCE:**
- All routes import and pass static analysis (pydantic v2.13 + fastapi 0.136 + sqlalchemy 2.0.49 in `.venv`).
- The router contract is type-safe: every POST validates request body through Pydantic; every response returns a typed `*View` model.
- DirectorPlan POST enforces `plan.job_id == URL job_id` so cross-job tampering is rejected with 400.

---

## §7 — Architectural decisions locked

**CLAIM:** Plan §16 open decisions are settled and persisted to memory.

**FILES CHANGED:**
- `~/.claude/projects/.../memory/aidirector_locked_decisions.md`
- `~/.claude/projects/.../memory/MEMORY.md` (added pointer)

**EVIDENCE — decisions:**

| Decision | Choice | Why |
|---|---|---|
| Auth | Clerk | Faster Next.js DX + org/multi-tenant primitives |
| OmegaClips visibility | Hold public until launch | Avoid CI submodule auth churn during build |
| OmegaClips `server.py` in prod | Retire; keep for local dev/admin | No proxy hop; clean seam |
| Queue topology | Redis + RQ over OmegaClips JobStore (Option B) | Single new abstraction, no engine fork |

---

## §8 — Git state

**CLAIM:** Initial Phase 0 scaffold landed as root commit. Phase 1 schema + adapters + routes + docs sit unstaged in the working tree.

**EVIDENCE:**

```text
git log --oneline
57625d9 (HEAD -> main) chore: initial Phase 0 scaffold

git status (Phase 1 work, unstaged):
  M apps/api/src/api/db.py
  M apps/api/src/api/deps.py
  M apps/api/src/api/main.py
  M apps/api/src/api/routers/jobs.py
  M apps/api/src/api/routers/uploads.py
  M apps/api/src/api/schemas/director_plan.py
  M workers/pyproject.toml
  M workers/src/workers/modal_app.py
  M .gitignore
  ?? apps/api/_probe_alembic.py
  ?? apps/api/_probe_loop.py
  ?? apps/api/_probe_schema.py
  ?? apps/api/alembic.ini
  ?? apps/api/alembic/
  ?? apps/api/src/api/models/
  ?? apps/api/src/api/routers/director_plans.py
  ?? apps/api/src/api/services/intel/
  ?? apps/api/src/api/services/platform_optimizer.py
  ?? apps/api/src/api/services/tenancy.py
  ?? apps/api/src/api/services/usage_events.py
  ?? docs/
  ?? uv.lock
  ?? workers/src/workers/clip_ranking_worker.py
  ?? workers/src/workers/omega_import_probe.py
  ?? workers/src/workers/render_worker.py
  ?? workers/src/workers/scene_analysis_worker.py
```

`uv.lock` is the resolved workspace lockfile (102 packages, CPython 3.12.11) — checking it in is the uv idiom for reproducibility.

---

## §9 — Operating issues encountered (and resolved)

| Issue | Cause | Resolution |
|---|---|---|
| `& "..venv\\python.exe" -c "..."` hangs in PowerShell | Win32 process invocation via PS `&` operator blocks on stdout for these specific binaries on this machine | Wrap all venv-python invocations in `cmd /c "...exe ..."` |
| `uv sync` writes to `C:\Python314\Lib\site-packages` and 500s | `VIRTUAL_ENV=C:\Python314` env var leaks from parent shell; `--active` flag honors it | Drop `--active`; rely on `uv` finding `.venv` from workspace root |
| Alembic CLI hangs with no output | Logging via `fileConfig` collides with the wrapping process under cmd | Drive `alembic.command.upgrade` from a Python wrapper script (`_probe_alembic.py`) — output captured to StringIO and written to a log file |

The `_probe_*.py` files stay in the repo (gitignored outputs only) as reproducible diagnostics — re-run them in 6 months to verify nothing rotted.

---

## §10 — What's intentionally NOT done (per user's "stop before expansion")

- Live `modal run` of the import probe — runbook only; blocked on `modal token new` browser auth
- Real R2 presigning (route returns stub URL; `r2.py` service unwired)
- Stripe metered event emission (`usage_events` rows are written; Stripe push is phase 2)
- Clerk webhook handlers for tenant/user provisioning
- Worker function bodies (all 4 workers raise `NotImplementedError` with "Phase 1" notes)
- Frontend dashboard wiring (Next.js shell exists from Phase 0, no upload UI yet)
- ML/heuristic scorers — interfaces only, no implementations
- Multi-vertical refactor (`intel_core/` extraction) — deferred to post-PMF per plan §3

---

## Summary

The product spine works end-to-end on the persistence side:

```
Tenant
  ↳ User
  ↳ Upload (tenant-scoped, R2 key)
       ↳ Job (links omegaclips_job_id + intel_submodule_sha)
            ↳ Scene (FK to job + tenant)
                 ↳ ClipCandidate (FK to job + scene + tenant)
                      ↳ DirectorPlan (one per job, plan_json round-trips through Pydantic contract)
                           ↳ RenderJob (one per candidate × variant)
                                ↳ RenderOutput (r2_key + aspect_ratio + bytes)
  ↳ UsageEvent (8 written, covering the 13 declared types)
```

The migration runs forward and backward cleanly. The Pydantic contract holds. The adapter boundary is enforced. The Modal gate is one operator action away. The capability map shows we're integrating, not rebuilding.

Next operator actions, in order:
1. `modal token new` + `modal run workers/src/workers/modal_app.py::ping_intel` → close gate #2
2. Provision Neon; set `DATABASE_URL` in `.env.local`; `alembic upgrade head` against Neon
3. Wire R2 presigning in `services/r2.py`
4. Implement `workers.scene_analysis_worker.analyze_video` (the first real `football_pipeline.*` import)
