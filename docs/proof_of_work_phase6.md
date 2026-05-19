# Proof of Work — Phase 6: ExportArtifact + Telemetry-Ready Export Tracking

**Session:** 2026-05-19
**Submodule:** packages/intel @ 78fcd57
**Prior commits:** 57625d9, 135c5ef, 0184125, 80528f7, 0c41614, 321be23

**Status: PASS (local).** Phase 6 probe exits 0 across six sub-tests (schema, hash determinism, storage URI + transport + lineage, persistence, idempotency / version bump, usage event with all required metadata keys). The canonical `ExportArtifact` layer is now real — analytics will attach here, never to `RenderOutput`.

---

## CLAIM

The product loop's *export variants → measure* transition is structurally ready. Every distributable asset has:

- **Immutable identity** — UUID PK, `export_hash` (deterministic from `render_output_id|platform|version`), `content_hash` (SHA256 of bytes)
- **Lineage** — FK to `render_outputs.id`, tenant_id mirrored
- **Versioning** — `export_version` bumps produce new `export_hash` while preserving `content_hash` for unchanged bytes
- **Storage URI** — scheme-aware, deterministic key shape, parseable into transport + path
- **Telemetry anchor** — every analytics row, retry, re-export, social-platform attribution lands on this row, not on render_outputs

The architecture honours the user's correction exactly: *analytics attaches to `ExportArtifact`, not `RenderOutput`*. Render layer stays renderer-only; export layer is the distributable identity; telemetry layer (Phase 7) will attach by FK to `exports.id`.

---

## FILES CHANGED

```
A apps/api/src/api/models/exports.py
M apps/api/src/api/models/__init__.py
A apps/api/alembic/versions/20260519_0002_exports.py
M apps/api/src/api/services/r2.py
A apps/api/src/api/services/export_artifact_builder.py
A apps/api/src/api/services/export_persistence.py
A workers/src/workers/export_worker.py
A apps/api/_probe_phase6_loop.py
A docs/proof_of_work_phase6.md
```

| File | Role |
|---|---|
| `models/exports.py` | `ExportArtifact` ORM model + `ExportArtifactStatus` enum. 6 indexes (tenant+platform, tenant+created_at, render_output_id, export_hash UNIQUE, content_hash, status) |
| `alembic/versions/20260519_0002_exports.py` | CREATE TABLE + 6 CREATE INDEX. Reversible (downgrade drops everything). |
| `services/r2.py` | **Promoted.** `is_r2_configured()`, `local_mirror_path()`, deterministic key builders, `build_storage_uri()`, `parse_storage_uri()`, `put_local_file()` (R2-or-local-mode dispatch), `presign_put`/`presign_get` with stub fallback. |
| `services/export_artifact_builder.py` | Pure function: RenderOutput → `ExportArtifactInputs` with deterministic filename, content_hash, export_hash, storage_uri, full metadata. Frozen dataclass keeps the payload safe across boundaries. |
| `services/export_persistence.py` | `persist_export_artifact(...)` inserts row + emits `EXPORT_CREATED`. `mark_export_failed`/`mark_export_published` for lifecycle. |
| `workers/export_worker.py` | Thin Modal shell: reads `RenderOutput`, calls builder, transports bytes via `put_local_file`, persists row. ~30 lines, zero hash/identity logic. |
| `_probe_phase6_loop.py` | Six sub-tests A–F. |

---

## EXACT COMMANDS RUN

```bash
cd "c:/Users/mican/Documents/AI Agent Director/apps/api"
rm -f _probe_phase6_loop.out
"../../.venv/Scripts/python.exe" _probe_phase6_loop.py
cat _probe_phase6_loop.out
```

Exit: **0**.

---

## ROOT CAUSE / DESIGN REASON

User's correction (verbatim): *"Analytics later will break unless every exported asset has immutable identity, lineage, provenance. Without ExportArtifact: TikTok upload, YouTube upload, re-export, watermark changes, retries, re-renders, A/B tests, analytics ingestion cannot map back cleanly. Do NOT attach analytics directly to RenderOutput rows."*

The architecture matches that mandate exactly:

```
RenderOutput          ← renderer's result (file + technical metadata)
       │
       ▼
ExportArtifactBuilder ← computes identity (hashes, filename, storage URI)
       │
       ▼
ExportArtifact        ← canonical distributable identity (DB row)
       │
       ▼
storage transport     ← r2.put_local_file (R2 mode or local-mode mirror)
       │
       ▼
EXPORT_CREATED        ← usage event with all 9 required metadata keys
       │
       ▼
(Phase 7) telemetry   ← attaches BY FK to exports.id, never to render_outputs.id
```

### Two-hash design (key insight)

| Hash | Computed from | Stable across | Drifts across |
|---|---|---|---|
| `export_hash` | `sha256(render_output_id \| platform \| export_version)` | same identity tuple | version bump, platform change, different render |
| `content_hash` | `sha256(file bytes)` | identical bytes (even cross-platform) | re-rendered bytes |

Why both? Because the use cases need different things:

- **Idempotent INSERT / retry safety** — same identity tuple must produce the same `export_hash`; UNIQUE index on it prevents double inserts.
- **Cross-platform attribution and dedup** — two platforms exporting the same file get *different* `export_hash` (different platform) but the *same* `content_hash`. Analytics across platforms can group by content.
- **Re-render detection** — bump `export_version`, re-build the artifact: new `export_hash`, same `content_hash` if bytes didn't change. New `export_hash`, new `content_hash` if they did.

### Two-mode r2 (key insight)

The Phase 0 r2.py stub eagerly created a boto3 client even without credentials. That made local probes uncallable. The promoted version:
- `is_r2_configured()` → bool gate on every operation
- `build_storage_uri()` returns `r2://…` or `local://…` based on the gate
- `put_local_file()` either uploads via boto3 or copies into a local mirror
- `parse_storage_uri()` is a pure function — same URI parses identically in both modes

Result: the same code path runs against `_local_storage/` in tests and against Cloudflare R2 in production. No conditional branching at the call site.

---

## EVIDENCE — `_probe_phase6_loop.out`

### Sub-test A — schema

```
A.tables=['alembic_version','clip_candidates','director_plans','exports','jobs',
          'render_jobs','render_outputs','scenes','tenants','uploads',
          'usage_events','users']
A.exports.cols=['artifact_metadata','content_bytes','content_hash','created_at',
                'export_hash','export_status','export_version','filename','id',
                'platform','published_at','render_output_id','storage_uri',
                'tenant_id','updated_at']
A.exports.indexes=['ix_exports_content_hash','ix_exports_export_hash',
                   'ix_exports_export_status','ix_exports_render_output_id',
                   'ix_exports_tenant_id_created_at','ix_exports_tenant_id_platform']
```

`exports` table now alongside the other 10 tables; 15 columns; 6 indexes. All required columns present.

### Sub-test B — hash + filename determinism

```
B.content_hash_a=c6440cd18f9dcec2ca395de003b9f4206dee9c5d954920fdb23076bddc6906c4
B.content_hash_b=c6440cd18f9dcec2ca395de003b9f4206dee9c5d954920fdb23076bddc6906c4
B.filename_a=phase6_probe_youtube_shorts_18df7b9c_v1.mp4
B.filename_b=phase6_probe_youtube_shorts_18df7b9c_v1.mp4
B.export_hash_a=4a0688a567c769279a68c7635edc38c65b9ef8cec6e3b18474de5cfd9eff7ca3
B.export_hash_b=4a0688a567c769279a68c7635edc38c65b9ef8cec6e3b18474de5cfd9eff7ca3
```

Two calls of `build_export_artifact` with the same `(render_output, candidate_id, platform, export_version)` produced byte-identical `content_hash`, `filename`, and `export_hash`. `export_id` is a fresh UUID per call (assertion in the probe verifies that — identity at the row level is the hash, not the PK).

### Sub-test C — storage URI + transport + parse

```
C.export_key=tenant/013e2cdf-…/exports/0e648b2b-…/phase6_probe_youtube_shorts_18df7b9c_v1.mp4
C.storage_uri=local://…/_storage/tenant/013e2cdf-…/exports/0e648b2b-…/phase6_probe_youtube_shorts_18df7b9c_v1.mp4
C.actual_uri_after_upload=local://…  (matches storage_uri)
C.parsed_scheme=local
C.stored_path.exists=True bytes=2043077
```

The `local://` URI parses cleanly, the file actually arrived at the parsed path, and its byte count matches `content_bytes`. Same code path will produce `r2://aidirector-prod/tenant/…/exports/…` once `R2_*` env vars are set.

### Sub-test D — persistence + lineage

```
D.persisted.id=0e648b2b-7ef3-484d-8631-6c63265e05f8
D.persisted.render_output_id=6553ed3c-a6f6-4e89-b72b-ea1115e307f0   ← lineage anchor
D.persisted.status=uploaded
D.persisted.platform=youtube_shorts
D.persisted.export_version=1
D.persisted.export_hash=4a06…       (same hex as B)
D.persisted.content_hash=c644…      (same hex as B)
D.persisted.filename=phase6_probe_youtube_shorts_18df7b9c_v1.mp4
D.persisted.storage_uri=local://…
```

Lineage FK is intact (`export.render_output_id == render_output.id`), tenant_id mirrored (assertion in the probe), all 9 fields populated.

### Sub-test E — version bump

```
E.v2.export_hash=569f55443113e253c57c0419cfb18578c0ec1515020ba0e49058f187db388577
E.v2.content_hash=c6440cd18f9dcec2ca395de003b9f4206dee9c5d954920fdb23076bddc6906c4
```

- `export_hash` changed (4a06… → 569f…) because `export_version` went 1 → 2
- `content_hash` is *byte-identical* (c644…) because the rendered file did not change

That's the proof the two-hash design carries the right semantics: re-export of the same bytes gets a new identity but is still recognisable as the same content.

### Sub-test F — EXPORT_CREATED usage event

```
F.usage_events=[["analysis_completed","scene"],["analysis_started","job"],
                ["candidate_created","candidate"],["director_plan_created","plan"],
                ["export_created","export"],
                ["ranking_completed","ranking"],
                ["render_completed","clip_seconds"],["render_started","render"],
                ["upload_created","upload"]]
F.export_created.count=1
F.export_created.metadata_keys=['content_bytes','content_hash','export_hash',
                                'export_id','export_version','filename','platform',
                                'render_output_id','storage_uri']
db.exports_count=1
```

`EXPORT_CREATED` joins the eight previously-emitted events from Phases 0–5. Metadata payload carries all 9 keys analytics will need to reconcile clicks/views/watch-time back to the export. Telemetry ingestion now has a clean attribution anchor.

---

## Schema linkage (FK chain verified end-to-end)

```
tenants
  └─> users
  └─> uploads
        └─> jobs (intel_submodule_sha from analyzer; status = SUCCEEDED)
              └─> scenes
                    └─> clip_candidates
              └─> director_plans (deterministic-builder/v1)
              └─> render_jobs (status = SUCCEEDED, cost_cents stamped)
                    └─> render_outputs (r2_key, bytes, output_metadata)
                          └─> exports  ← NEW PHASE 6 LAYER
                                       │  export_hash UNIQUE
                                       │  content_hash for dedup/attribution
                                       │  storage_uri + filename + version
              └─> usage_events
                    upload_created
                    analysis_started / analysis_completed
                    ranking_started / candidate_created (×N) / ranking_completed
                    director_plan_created
                    render_started / render_completed
                    export_created  ← NEW
```

The chain is now five tables deep before the export row, and every row carries `tenant_id` for clean multi-tenant isolation.

---

## Storage URI examples (one row, two transport modes)

**Local-mode (probe):**
```
local://C:/Users/mican/Documents/AI Agent Director/apps/api/_probe_phase6_fixtures/
        _storage/tenant/013e2cdf-eec2-4736-ae29-908c93a5da02/exports/
        0e648b2b-7ef3-484d-8631-6c63265e05f8/
        phase6_probe_youtube_shorts_18df7b9c_v1.mp4
```

**R2-mode (production — same code path):**
```
r2://aidirector-prod/tenant/013e2cdf-eec2-4736-ae29-908c93a5da02/exports/
     0e648b2b-7ef3-484d-8631-6c63265e05f8/
     phase6_probe_youtube_shorts_18df7b9c_v1.mp4
```

`parse_storage_uri` returns the right transport + key in both cases. The probe asserts the local mode resolves correctly; the R2 mode is wired through the same function with no branching at the call site.

---

## Worker stays a thin shell

[workers/src/workers/export_worker.py](../workers/src/workers/export_worker.py)

```python
@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def create_export_artifact_fixture(
    render_output_id: str, candidate_id: str, tenant_slug: str,
    platform: str, local_source_path: str, export_version: int = 1,
) -> dict:
    with Session(engine) as db:
        ro = db.execute(select(RenderOutput).where(...)).scalar_one()
        job = db.execute(select(Job).where(...).order_by(...).limit(1)).scalar_one()
        inputs = build_export_artifact(...)
        put_local_file(Path(local_source_path), key)
        row = persist_export_artifact(db, job=job, render_output=ro, inputs=inputs)
        db.commit()
        return {...}
```

Worker logic: lookup row, build identity, transport bytes, persist row, return. **No hashing, no path building, no usage events** — those live in `export_artifact_builder` and `export_persistence` respectively.

---

## Acceptance — every Phase 6 criterion mapped to evidence

| Criterion | ✅ | Evidence |
|---|---|---|
| `_probe_phase6_loop.py` exits 0 | ✓ | confirmed |
| `ExportArtifact` rows persist correctly | ✓ | sub-test D, `db.exports_count=1` |
| `EXPORT_CREATED` usage event emitted | ✓ | sub-test F, count=1 with all required metadata keys |
| `content_hash` generated deterministically | ✓ | sub-test B, identical 64-char hex across two calls |
| Deterministic filename generation works | ✓ | sub-test B, identical filename across two calls; format is `{slug}_{platform}_{short_cand}_v{n}.{ext}` |
| Storage URI generated correctly | ✓ | sub-test C, parseable, points at real file with matching bytes |
| Export lineage to `RenderOutput` verified | ✓ | sub-test D, `export.render_output_id == render_output.id`; FK enforced at DB level |
| Worker remains thin shell | ✓ | ~30 lines, zero identity logic |
| Proof report CLAIM / FILES / COMMANDS / ROOT CAUSE / EVIDENCE | ✓ | all 5 sections present |

---

## Modal cloud — explicit status (unchanged)

| Aspect | Status |
|---|---|
| Local export builder + persistence + storage transport | ✅ proven (this probe) |
| Modal cloud execution of `create_export_artifact_fixture` | ⏳ pending operator `modal token new` + `modal run` |
| Real R2 upload after render success | ⏳ flips automatically when `R2_*` env vars set; same code path |
| Phase 6.5 full DB-driven `export_worker` reading from RenderOutput by ID | ⬜ deferred |

The `r2.put_local_file` function picks transport mode at call time. Setting `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` in `.env.local` is the only change required for cloud R2 to take over — no code change.

---

## Architectural pattern catalog (now 7 patterns)

1. OmegaClips integration via runtime `submodule_path` insert (Phases 2, 3)
2. Adapter boundary enforcement
3. Persistence-service-per-phase
4. Thin Modal worker shell
5. AI-output sandboxing (Phase 4)
6. Two-layer execution contract (Phase 5)
7. **Canonical distributable identity** (Phase 6) — separate the renderer's result from the user-facing publishable identity; attach analytics by FK to the identity layer, never to the renderer layer

Each new phase has added exactly one architectural pattern that compounds with the prior six. The reusable shape of "schema row + builder + persistence + thin worker + probe" is now copy-pasteable for every future capability.

---

## Product loop status

```
understand video  →  rank moments  →  direct edits  →  export variants  →  measure  →  improve
       ✅                ✅                ✅                 ✅              🟡         ⬜
   Phase 2 PASS      Phase 3 PASS      Phase 4 PASS      Phase 5 PASS    Phase 6     not yet
                                                                          identity
                                                                          ready
```

The **identity** half of *measure* is closed. The **ingestion** half (clicks / views / watch-time attaching to `exports.id`) is the next Phase 7 work. Until then: every distributable asset has a stable place for analytics rows to land.

---

## What's intentionally NOT done

Per the user's "do not build" list for Phase 6:
- Social posting (YouTube / TikTok / IG / X APIs)
- Engagement predictor
- ML feedback systems
- Analytics dashboards
- Auto-crop engine
- Template marketplace
- Modal cloud execution of the export worker (operator action)
- Real R2 upload with credentials (env-var flip only, no code change)

Phase 7 picks up: ingestion adapter for per-platform engagement signals → write to a new `engagement_events` table → FK to `exports.id` → ranker reads aggregates to update its scoring.

---

## Reproducibility

```powershell
cd "c:\Users\mican\Documents\AI Agent Director\apps\api"
Remove-Item _probe_phase6_loop.out -ErrorAction SilentlyContinue
..\..\.venv\Scripts\python.exe _probe_phase6_loop.py
Get-Content _probe_phase6_loop.out
```

First run generates the 30-second test source and a local storage mirror under `_probe_phase6_fixtures/`. Subsequent runs reuse them. Same `.venv` and `packages/intel @ 78fcd57` as the earlier probes. Real FFmpeg required for the embedded Phase 5 step (already verified earlier in the session).
