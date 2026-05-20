# Phase 9.5 — Real UI/Backend Wiring (proof of work)

**Goal.** Replace the fixture-backed UI with real backend composite data
while preserving the frontend architecture firewall set up in Phase 9.

**Status:** PASS. All seven Phase 9.5 tasks landed, three probes pass
(`_probe_full_schema`, `_probe_phase9_5_jobview`, `_probe_schema`),
TypeScript typecheck is clean, `next build` succeeds for 12 routes, and
the firewall grep returns empty: no component touches `fetch`,
`setInterval`, `setTimeout`, `new ApiClient`, or `getToken` directly.

---

## What shipped

### 1. `apps/api/_probe_full_schema.py` — Alembic-applied schema proof

The base-model probe (`_probe_schema.py`) only sees the 10 tables
registered with `Base.metadata.create_all`. The new full-schema probe
runs `alembic upgrade head` against a fresh SQLite DB, then asserts:

- **15 application tables** present and *exactly that set* (no orphans).
- **9 critical indexes** present, with `unique=True` honoured where
  required:
  - `exports.ix_exports_export_hash` (unique)
  - `exports.ix_exports_content_hash`
  - `performance_feature_sets.ix_pfs_export_id_feature_version` (unique)
  - `ranking_snapshots.ix_ranking_snapshots_candidate_feature_version` (unique)
  - tenant-scoped read indexes on `uploads`, `jobs`, `engagement_events`,
    `usage_events`, `performance_feature_sets`.
- **28 foreign-key chains** validated: every tenant_id FK, the full
  pipeline chain (`jobs → uploads`, `scenes/clip_candidates → jobs`,
  `render_jobs → clip_candidates`, `render_outputs → render_jobs`),
  the export + telemetry chain
  (`exports → render_outputs`, `engagement_events → exports`,
  `performance_feature_sets → exports → experiment_groups`),
  and the ranking back-references
  (`ranking_snapshots → clip_candidates / jobs / exports`).

Distinct exit codes per assertion (6/7/8/9/10) so a regression points
straight at the failing predicate.

```
$ uv run python _probe_full_schema.py
rc=0
alembic_version=0004
PASS all 15 application tables present
PASS table count exact: 15 application tables
PASS index exports.ix_exports_export_hash (unique=1, cols=['export_hash'])
PASS index exports.ix_exports_content_hash (unique=0, cols=['content_hash'])
PASS index performance_feature_sets.ix_pfs_export_id_feature_version (unique=1, cols=['export_id', 'feature_version'])
PASS index ranking_snapshots.ix_ranking_snapshots_candidate_feature_version (unique=1, cols=['candidate_id', 'feature_version'])
…
PASS fk ranking_snapshots.source_export_id -> exports
OK
```

### 2. `_probe_schema.py` reframed

Updated docstring makes the narrower scope explicit and points readers
to `_probe_full_schema.py` for the authoritative schema proof.

### 3. `JobView` Pydantic composite — `apps/api/src/api/schemas/job_view.py`

One module, one composite. Fields mirror `apps/web/lib/api/types.ts::JobView`
bit-for-bit. Per-row sub-schemas use `extra="forbid"` so unexpected
backend fields fail loudly instead of leaking to the client.

`PerformanceFeatureViewRow` is the 12-field trust-gradient projection
exactly. Raw `engagement_events` rows are **not** part of the JobView —
the wire shape literally cannot expose them.

A second model, `JobEventsView`, is the polling-friendly status refresh:
`{job_id, status, revision, last_event_at, last_event_type, counts}`.

### 4. `GET /api/jobs/{id}/view` + `GET /api/jobs/{id}/events`

Both routes live in `apps/api/src/api/routers/jobs.py`, both 404 if the
job doesn't belong to the authenticated tenant, both delegate to
`api.services.job_view_service`:

- `build_job_view` — one SELECT per logical table, all tenant-scoped.
  Returns `JobView | None`.
- `build_job_events` — counts + most recent usage event. `revision` is
  the monotonic usage_event count, so a single check on the cheap
  endpoint tells the client whether to refetch the full view.

The existing single-row `JobView` Pydantic class in the router was
renamed to `JobRowOut` to free the name for the composite. Pre-existing
bugs in `billing.py` and `exports.py` (importing `Tenant` instead of
`Tenant_` — the orm class vs the str alias) were fixed in passing,
otherwise the app failed to import.

```
GET /api/jobs                              # list (unchanged)
GET /api/jobs/{id}                         # row (unchanged)
GET /api/jobs/{id}/view                    # NEW — composite
GET /api/jobs/{id}/events                  # NEW — polling refresh
GET /api/jobs/{id}/director-plan           # unchanged
POST /api/jobs                             # create (unchanged)
POST /api/jobs/{id}/director-plan          # plan (unchanged)
```

### 5. `apps/api/_probe_phase9_5_jobview.py` — end-to-end seed + read

Seeds a complete trajectory (2 scenes, 1 candidate, 1 director plan,
1 render job, 1 render output, 1 export, 1 experiment group,
1 performance feature set, 1 ranking snapshot, 11 usage events) for one
tenant, plus a foreign tenant for isolation, then calls
`build_job_view` and `build_job_events` and asserts:

| # | Assertion | Result |
|---|-----------|--------|
| A | `build_job_view` returns `JobView` | PASS |
| B | every collection length matches what was seeded | PASS (`scenes=2, candidates=1, render_jobs=1, render_outputs=1, exports=1, feature_views=1, snapshots=1, usage_events=11`) |
| C | `feature_views` is exactly 12 fields, no raw engagement leak | PASS |
| D | ranking snapshot preserves Phase 8 fields (`base=0.394, adj=0.096, final=0.49, cap=0.15, threshold=0.30, feedback_applied=True`) | PASS |
| E | director plan deserialises through the Pydantic contract | PASS (`version=1, selected=1, variants=1`) |
| F | tenant isolation: `tenant_b` cannot see `tenant_a`'s job | PASS |
| G | `build_job_events.counts` agrees with `len(view.*)` for every collection + `revision == len(usage_events)` | PASS (`revision=11, last_event=ranking_feedback_applied`) |
| H | `JobView.model_dump(mode="json")` round-trips through `json.dumps/loads` cleanly with the expected 11 top-level keys | PASS (`9680 bytes`) |

### 6. Frontend wired to real endpoints, fixture-fallback only

**`apps/web/lib/api/runtime.ts`** — new client-side factory. `useApi()`
returns `{endpoints, mode, baseUrl}`. Mode is `"live"` when
`NEXT_PUBLIC_API_URL` is set and non-empty, `"fixtures"` otherwise.
Hooks call `useApi()`; no component constructs an `ApiClient`.

**`apps/web/hooks/useJobView.ts`** — rewritten:

1. In `fixtures` mode → serves `FIXTURE_JOB_VIEW` directly, no network.
2. In `live` mode → polls `/api/jobs/{id}/events` every 4s. When
   `revision` changes (or on first load), refetches the full
   `/api/jobs/{id}/view`. This is bandwidth-proportional to pipeline
   progress, not wall-clock time.
3. If a live call throws, the hook surfaces the fixture and sets
   `fixturesUsed=true` so the UI can render a "demo data" banner
   without breaking.

**`apps/web/hooks/useRecentJobs.ts`** — same pattern: live `listJobs()`
with fixture fallback on error or fixture mode.

**`apps/web/services/job-events.ts`** — `PollingTransport` upgraded to
the same two-tier strategy (cheap `/events` heartbeat + view refetch on
revision change) so an external subscriber gets identical semantics to
the hook. `WebSocketTransport` interface unchanged.

**`apps/web/lib/api/endpoints.ts`** — added `getJobEvents(jobId)`.
**`apps/web/lib/api/types.ts`** — added `JobEvents` interface mirroring
the new Pydantic schema.
**`apps/web/lib/api/index.ts`** — re-exports `JobEvents`.

### 7. Architectural firewall — held

```
$ grep -rn "\bfetch\b\|setInterval\|setTimeout\|new ApiClient\|getToken()" \
    app/ components/ features/ stores/ --include="*.ts" --include="*.tsx"
(no matches)
```

Every component renders props or hook return values. Transport, polling,
auth, and fixture-fallback policy all live in `hooks/` + `services/` +
`lib/api/` — exactly the boundary set up in Phase 9.

---

## Build verification

```
$ npx tsc --noEmit
rc=0

$ NEXT_PUBLIC_API_URL="" NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=… \
  CLERK_SECRET_KEY=sk_test_dummy npx next build
✓ Compiled successfully in 15.8s
✓ Generating static pages (4/4)
Route (app)                                 Size  First Load JS
┌ ƒ /                                      404 B         146 kB
├ ○ /_not-found                            995 B         103 kB
├ ƒ /app                                   127 B         103 kB
├ ƒ /app/clips                           3.81 kB         188 kB
├ ƒ /app/director                          127 B         103 kB
├ ƒ /app/director/[jobId]                 5.6 kB         186 kB
├ ƒ /app/jobs                            1.34 kB         150 kB
├ ƒ /app/jobs/[id]                       3.39 kB         184 kB
├ ƒ /app/performance                     4.52 kB         150 kB
├ ƒ /app/renders                         5.07 kB         150 kB
├ ƒ /app/upload                          7.84 kB         183 kB
└ ƒ /dashboard                             395 B         143 kB
```

12 routes, all the dashboard surfaces dynamic where they need to be,
static landing + 404. No type errors in the wired hooks or in the new
Pydantic↔TypeScript bridge.

---

## What is intentionally not done

- **Modal cloud proof + R2 wiring.** The user gated this for after
  Phase 9.5, and it is the real deployment gate.
- **YouTube/TikTok connectors, Stripe, admin panel, ML, auto-posting.**
  Phase 10+ territory; the locked decisions document hasn't changed.
- **WebSocket transport.** The `WebSocketTransport` class is in place
  in `services/job-events.ts` with the same interface; switching the
  provider is a one-line change. Polling is plenty fast for now.
- **A real "demo data" banner in the UI.** `fixturesUsed` is exposed by
  both hooks but no consumer surfaces it yet — that's a UI polish task
  separate from the wiring.

---

## File inventory

New:
- `apps/api/_probe_full_schema.py`
- `apps/api/_probe_phase9_5_jobview.py`
- `apps/api/src/api/schemas/job_view.py`
- `apps/api/src/api/services/job_view_service.py`
- `apps/web/lib/api/runtime.ts`
- `docs/proof_of_work_phase9_5.md` (this file)

Modified:
- `apps/api/_probe_schema.py` — docstring reframed
- `apps/api/src/api/routers/jobs.py` — renamed `JobView` → `JobRowOut`,
  added `/view` + `/events` endpoints
- `apps/api/src/api/routers/billing.py` — `Tenant` → `Tenant_`
- `apps/api/src/api/routers/exports.py` — `Tenant` → `Tenant_`
- `apps/web/hooks/useJobView.ts` — real polling + fixture fallback
- `apps/web/hooks/useRecentJobs.ts` — real listing + fixture fallback
- `apps/web/services/job-events.ts` — two-tier polling
- `apps/web/lib/api/types.ts` — added `JobEvents`
- `apps/web/lib/api/endpoints.ts` — added `getJobEvents`
- `apps/web/lib/api/index.ts` — re-export `JobEvents`

---

## Next gate

Phase 9.5 is green. Per the locked plan: **Modal cloud proof + R2** is
the next gate, not Phase 10 platform connectors. The schema, contracts,
and wiring needed to support a Modal-side run are all in place — the
remaining work is operational (deploy `modal_app.py`, configure R2
bucket + IAM, replace the local-equivalent worker drives with real
Modal calls).
