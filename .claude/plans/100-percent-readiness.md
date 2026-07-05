# AI Director — 100% Engineering & Deployment Readiness Plan

**Combined from:** runtime audit (June 2026) + AURA best-in-class plan  
**Goal:** Ship a production-grade, cost-aware, auditable AI video pipeline with zero silent failures.

---

## Reality check: what works vs. what's missing

| Layer | Status |
|---|---|
| FastAPI app, Postgres schema, Clerk auth, Stripe billing | ✅ Wired |
| RenderManifest schema + FFmpeg execution (`render_plan_adapter`) | ✅ Solid |
| Renderer registry, platform optimizer, director_plan_builder | ✅ Solid |
| `transcribe.py`, `clip_format.py`, `viral_title.py` | ✅ Implemented, ❌ not wired to API |
| `_run_four_vertical_clips.py` demo (correct pipeline blueprint) | ✅ Works standalone, ❌ not a production path |
| Modal worker app (`apps/api/workers/`) | ❌ Missing entirely |
| Job queue wiring (`jobs.py:77` is a stub comment) | ❌ Missing |
| `render_manifest_builder._build_one()` populates title/subtitle_uri | ❌ Never set — title/subtitle burning dead in API path |
| CORS for production | ❌ `allow_origins=[]` in non-dev — blocks frontend |
| `RENDER_MANIFEST_VERSION` bumped after schema change | ❌ Still "1" |
| `faster-whisper` in pyproject.toml | ❌ Missing |
| Observability (Sentry, Logfire, structured logging) | ⚠️ Wired in deps, not in services |
| CI / test suite | ❌ No tests found |
| Provenance / signed artifacts | ❌ Not started |
| Brief template library (DirectorPlan templates) | ❌ Not started |

---

## Phase 0 — Bug Fixes (Day 1–2) · Block nothing from going to prod

These are blocking correctness issues solvable in < 2 hours total.

### P0-1: Bump schema version
**File:** `apps/api/src/api/schemas/render_manifest.py:35`
```python
RENDER_MANIFEST_VERSION = "2"  # was "1" — bumped when title/subtitle_uri added
```
Add a migration comment explaining what changed and what backfill means for existing queued jobs (`title=None, subtitle_uri=None` — safe, both are optional).

### P0-2: Add faster-whisper as optional dependency
**File:** `apps/api/pyproject.toml`
```toml
[project.optional-dependencies]
asr = ["faster-whisper>=1.0"]
```
Document: `pip install api[asr]` or `uv sync --extra asr` to enable real transcription. Without it, the fallback SRT path runs (already correct behavior, now explicit).

### P0-3: Add structured logging to transcribe.py fallbacks
**File:** `apps/api/src/api/services/transcribe.py`  
Import `logging` and emit `logger.warning(...)` at each fallback branch (ImportError, ffmpeg failure, model crash, no speech). Ops visibility — currently all failures are silent.

### P0-4: Fix type hint on `read_srt_text`
**File:** `apps/api/src/api/services/viral_title.py:231`
```python
def read_srt_text(srt_path: str | Path) -> str:
```

### P0-5: Fix production CORS
**File:** `apps/api/src/api/main.py:22`
```python
allow_origins=settings.allowed_origins  # was: [] hardcoded for non-dev
```
**File:** `apps/api/src/api/config.py` — add:
```python
allowed_origins: list[str] = ["http://localhost:3000"]
```
**File:** `.env.example` — add:
```
ALLOWED_ORIGINS=https://app.aidirector.com,https://aidirector.vercel.app
```
This is a silent outage in production — the frontend cannot reach the API.

---

## Phase 1 — Pipeline Wiring (Week 1) · The core product must work end-to-end

This is the highest-value phase. The render infrastructure exists; the wiring does not.

### P1-1: Wire title + subtitle into `render_manifest_builder`

**File:** `apps/api/src/api/services/render_manifest_builder.py`

The builder currently receives `source_uri` and `plan`. Add two new optional params to `build_manifests()`:
```python
def build_manifests(
    *,
    plan: DirectorPlan,
    source_uri: str,
    source_duration_s: float | None = None,   # NEW — for title/sub generation
    tenant_id: str,
    tenant_slug: str,
    srt_output_dir: Path | None = None,        # NEW — where to write .srt files
) -> ManifestBuildResult:
```

In `_build_one()`, call `transcribe_to_srt()` and `build_title()` from the new services when `srt_output_dir` is provided. This keeps backward compatibility (callers that don't pass these args get `title=None, subtitle_uri=None` as before).

**Important:** transcription is I/O-bound and slow. `_build_one()` should not block synchronously in the builder. See P1-3 (worker) for how this runs in the background.

### P1-2: Create the render RQ worker

**New file:** `apps/api/workers/render_worker.py`

This is the blueprint from `_run_four_vertical_clips.py` ported to a real worker:

```python
"""RQ worker function: consume a render job from q:render-cpu."""
from api.schemas.render_manifest import RenderManifest
from api.services.intel.render_plan_adapter import render_clip
from api.services.render_output_persistence import persist_render_output
from api.services.transcribe import transcribe_to_srt
from api.services.viral_title import TitleHints, build_title, read_srt_text

def execute_render_job(job_payload: dict) -> dict:
    manifest = RenderManifest.model_validate(job_payload["manifest"])
    # 1. Transcribe if caption_mode != "off" and subtitle_uri not already set
    # 2. Build title via viral_title if title not already set
    # 3. Re-validate manifest with populated fields
    # 4. Call render_clip(manifest, output_dir=...)
    # 5. Persist RenderExecutionResult via render_output_persistence
    # 6. Return result dict (RQ stores it in job.result)
```

The worker pattern mirrors the demo script exactly — that script is the design doc for this worker.

### P1-3: Wire the job queue in `jobs.py`

**File:** `apps/api/src/api/routers/jobs.py:77`

Replace the stub comment:
```python
# Phase 1: enqueue Modal worker here
# queue.enqueue("scene_analysis", {"job_id": str(job.id), ...})
```
With:
```python
from api.services.queue import queue_for
q = queue_for("render-cpu")
q.enqueue(
    "workers.render_worker.execute_render_job",
    {"job_id": str(job.id), "upload_id": str(req.upload_id)},
    job_timeout=300,
    result_ttl=86400,
)
```

The worker fetches the DirectorPlan from the DB by job_id, builds manifests, and executes.

### P1-4: Create a `/api/renders` router

**New file:** `apps/api/src/api/routers/renders.py`

Endpoints:
- `GET /api/renders?job_id=<uuid>` — list all RenderExecutionResults for a job
- `GET /api/renders/{render_job_id}` — single render result
- `GET /api/renders/{render_job_id}/download` — pre-signed R2 URL

Register in `main.py`. The `render_output_persistence.py` service already exists — this router just surfaces it.

### P1-5: Promote `_run_four_vertical_clips.py` to a proper integration test

Move to `apps/api/tests/integration/test_four_vertical_clips.py` and gate behind `pytest.mark.integration` (skipped in CI unless `SOURCE_VIDEO` env var is set). Delete the underscore-prefixed script. This validates the entire render stack.

---

## Phase 2 — Worker Infrastructure (Week 1–2)

### P2-1: Create Modal worker app

**New file:** `apps/api/modal_app.py`

The architecture decision (memory: locked 2026-05-18) chose Redis+RQ over OmegaClips JobStore. Modal provides the compute; RQ provides the queue. The worker app:

```python
import modal
from api.services.queue import queue_for

app = modal.App("aidirector-workers")

intel_image = (
    modal.Image.debian_slim()
    .apt_install("ffmpeg")
    .pip_install("faster-whisper", "rq", "redis")
    .pip_install_from_pyproject("apps/api/pyproject.toml")
)

@app.function(image=intel_image, timeout=300, memory=2048)
def render_worker():
    """Pop one render job from RQ and execute it."""
    from workers.render_worker import execute_render_job
    # RQ worker loop (one job per invocation for Modal's stateless model)
    ...
```

Add Modal deploy instructions to README and `.env.example` (`MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`).

### P2-2: Worker health endpoint

**File:** `apps/api/src/api/routers/health.py`  
Add a `/health/queue` endpoint that checks Redis connectivity and reports queue depths for `q:render-cpu`, `q:llm`, `q:export`. Already have Redis in deps — this is a 15-line addition.

### P2-3: Idempotency on re-enqueue

The `idempotency.py` service already exists. Use it in the render worker to prevent double-renders if RQ retries a job after a transient failure.

---

## Phase 3 — Provenance / Signed Artifacts (Week 2)

**Adapted from AURA plan.** This project has signed render outputs as a trust moat — clients need proof that a clip came from their upload, not a substitute video.

### P3-1: Render manifest signer

**New file:** `apps/api/src/api/services/provenance.py`

```python
"""Ed25519 signing for rendered artifacts.

Manifest JSON follows C2PA top-level structure so upgrade to c2pa-python
is mechanical later. Key fields:
  assertions: list of claim objects (source_uri, clip_window, renderer, tenant_id)
  signature: base64(ed25519.sign(sha256(canonical_json(assertions))))
  metadata: {created_at, version, signer_key_id}
"""
```

`to_c2pa() -> dict` method returns a C2PA-compatible JSON. The signature is stored on `RenderOutput` row and included in the `/api/renders/{id}/download` response headers (`X-AURA-Provenance`).

### P3-2: Key management

Store the Ed25519 private key as a secret (`PROVENANCE_SIGNING_KEY_B64`) in Modal secrets and `.env.example`. Never log it. Rotate via re-signing existing manifests (add a `POST /api/admin/resign` endpoint behind an admin-only middleware).

### P3-3: Schema for provenance

**New file:** `apps/api/src/api/schemas/provenance_manifest.py`  
Pydantic model matching the C2PA JSON structure. Validate generated manifests against it in tests.

---

## Phase 4 — Brief Template Library (Week 2–3)

**Adapted from AURA plan's "Prompt Library."** For this project, the equivalent is a library of reusable DirectorPlan briefs — sport context, style presets, pacing preferences. This is a product moat: an operator can build a sports team's "house style" and reuse it across every game.

### P4-1: Data model

**New migration:** Add `brief_templates` table:
```sql
CREATE TABLE brief_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name TEXT NOT NULL,
    description TEXT,
    sport TEXT,                   -- "football", "basketball", etc.
    render_style TEXT,            -- maps to RenderStyle
    caption_style TEXT,
    pacing TEXT,                  -- "fast" | "medium" | "slow"
    hook_phrases JSONB,           -- list of preferred hook options
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### P4-2: CRUD API

**New file:** `apps/api/src/api/routers/brief_templates.py`

Endpoints:
- `POST /api/brief-templates` — create
- `GET /api/brief-templates` — list (filterable by sport, tags)
- `GET /api/brief-templates/{id}` — get one
- `PATCH /api/brief-templates/{id}` — update
- `DELETE /api/brief-templates/{id}` — delete

### P4-3: Apply template at job creation

**File:** `apps/api/src/api/routers/jobs.py` — add optional `brief_template_id` to `JobCreate`. If present, merge template fields into the DirectorPlan brief before analysis.

### P4-4: Frontend: Template Library tab

**New file:** `apps/web/src/app/(dashboard)/templates/page.tsx`  
Searchable list, preview panel, "Use in new job" CTA. Mirrors the AURA plan's Prompt Library UI concept but implemented in Next.js (not Streamlit).

---

## Phase 5 — Observability & Hardening (Week 3)

### P5-1: Structured logging in all services

Every service in `apps/api/src/api/services/` should use `logfire` structured logging (already in deps). Key events:
- `render_clip` start/end with manifest fields and elapsed time
- Worker job pick-up and completion
- ASR engine selected (faster-whisper vs fallback)
- Provenance signing success/failure

### P5-2: Sentry integration

`SENTRY_DSN` is in `.env.example` but never wired in `main.py`. Add:
```python
import sentry_sdk
sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
```
Wire to the RQ worker as well.

### P5-3: Harden Windows font probe

**File:** `apps/api/src/api/services/intel/render_plan_adapter.py:152`

The `_find_drawtext_font()` function probes hardcoded paths at module import time. Change to:
1. Accept optional `FFMPEG_DRAWTEXT_FONT` env var override (highest priority)
2. Probe the existing candidate list as fallback
3. Log a `logger.warning()` when no font is found (currently silent)
4. In CI, assert that at least one font resolves on the test runner

### P5-4: Model cache eviction

**File:** `apps/api/src/api/services/transcribe.py:20`

In a Modal stateless worker, the global `_MODEL` cache is fine (process dies after each job). In a long-running FastAPI server it's fine too (we want it loaded once). But add a `release_model()` function for test isolation so tests can reset state between runs.

### P5-5: next.config.ts tracing validation

Add a CI step (`npm run build`) that fails fast if the `outputFileTracingRoot` change breaks the Next.js build. Currently there is no build validation in CI.

---

## Phase 6 — Test Suite (Week 3–4)

Target: **pytest coverage ≥ 85%** on the services layer, ≥ 60% overall.

### P6-1: Unit tests — new services

```
apps/api/tests/unit/
  test_clip_format.py       # pick_short_form_duration coverage + edge cases
  test_viral_title.py       # build_title with goal/save/skill/fail/fallback transcripts
  test_transcribe.py        # fallback SRT writing, _format_srt_ts, _extract_audio_slice mock
  test_render_manifest_builder.py  # title/subtitle_uri population, schema version assertion
```

### P6-2: Unit tests — existing services (gap-fill)

```
  test_render_plan_adapter.py   # dry_run=True covers command construction determinism
  test_provenance.py            # manifest validates against C2PA schema
  test_brief_templates.py       # CRUD service-layer tests
```

### P6-3: Integration test — render pipeline

`apps/api/tests/integration/test_render_pipeline.py` (promoted from `_run_four_vertical_clips.py`):
- Skipped unless `SOURCE_VIDEO` is set
- Validates: 4 clips rendered, non-empty, signed manifest present

### P6-4: CI configuration

**New file:** `.github/workflows/ci.yml`

```yaml
jobs:
  api-test:
    - uv sync --extra asr
    - pytest apps/api/tests/unit/ --cov=api --cov-report=xml
    - pytest apps/api/tests/integration/ -m "not integration"  # skip real renders
  web-build:
    - pnpm install
    - pnpm build          # validates next.config.ts change
    - pnpm tsc --noEmit   # typed routes check
```

---

## Phase 7 — Deployment Readiness (Week 4)

### P7-1: Docker image for the API

**New file:** `apps/api/Dockerfile`

```dockerfile
FROM python:3.12-slim
RUN apt-get install -y ffmpeg
COPY pyproject.toml .
RUN pip install .[asr]
COPY src/ src/
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### P7-2: Production env var checklist

The following must be set before a deploy is healthy. Add a startup check in `lifespan()` that logs errors for missing critical vars:

| Var | Required for |
|---|---|
| `DATABASE_URL` | All DB operations |
| `REDIS_URL` | Job queue |
| `R2_*` (5 vars) | Upload/download storage |
| `CLERK_*` (3 vars) | Auth |
| `STRIPE_*` (6 vars) | Billing |
| `ALLOWED_ORIGINS` | CORS |
| `ANTHROPIC_API_KEY` | Director Agent LLM calls |
| `SENTRY_DSN` | Error tracking |
| `LOGFIRE_TOKEN` | Structured logging |
| `MODAL_TOKEN_*` | Worker compute |
| `PROVENANCE_SIGNING_KEY_B64` | Signed artifacts |

### P7-3: Alembic migration baseline

Confirm all current models have migrations. Run `alembic check` in CI to catch drift between models and migration history.

### P7-4: Deployment runbook

**New file:** `docs/DEPLOY.md`

Covers: Modal deploy, RQ worker start, Next.js deploy to Vercel/Cloudflare Pages, DB migration, Stripe webhook registration, Clerk webhook registration.

---

## Consolidated ticket list (priority order)

### Sprint 1 — Unblock prod (Week 1)
| ID | Work | File(s) | Hours |
|---|---|---|---|
| S1-1 | Bump RENDER_MANIFEST_VERSION to "2" | render_manifest.py:35 | 0.25 |
| S1-2 | Fix production CORS | main.py, config.py, .env.example | 0.5 |
| S1-3 | Add faster-whisper optional dep | pyproject.toml | 0.25 |
| S1-4 | Log transcribe fallbacks | transcribe.py | 0.5 |
| S1-5 | Fix read_srt_text type hint | viral_title.py:231 | 0.1 |
| S1-6 | Wire title+subtitle into builder | render_manifest_builder.py | 3 |
| S1-7 | Create render RQ worker | workers/render_worker.py | 4 |
| S1-8 | Wire queue in jobs.py | routers/jobs.py:77 | 1 |
| S1-9 | Create /api/renders router | routers/renders.py | 2 |
| S1-10 | Unit tests: clip_format, viral_title | tests/unit/ | 2 |

### Sprint 2 — Pipeline complete (Week 2)
| ID | Work | Hours |
|---|---|---|
| S2-1 | Modal worker app | 4 |
| S2-2 | Worker health endpoint | 1 |
| S2-3 | Idempotency in render worker | 1 |
| S2-4 | Provenance signer + schema | 4 |
| S2-5 | Ed25519 key management + env | 1 |
| S2-6 | Brief template data model + migration | 2 |
| S2-7 | Brief template CRUD API | 3 |
| S2-8 | Unit tests: provenance, transcribe | 2 |

### Sprint 3 — Quality (Week 3)
| ID | Work | Hours |
|---|---|---|
| S3-1 | Structured logfire logging in all services | 3 |
| S3-2 | Sentry wired (API + worker) | 1 |
| S3-3 | Font probe hardening + env override | 1 |
| S3-4 | CI workflow (GitHub Actions) | 2 |
| S3-5 | Brief Template Library frontend tab | 4 |
| S3-6 | Unit tests: render_plan_adapter (dry_run) | 2 |
| S3-7 | Integration test: full render pipeline | 2 |

### Sprint 4 — Ship (Week 4)
| ID | Work | Hours |
|---|---|---|
| S4-1 | Dockerfile for API | 2 |
| S4-2 | Startup env var validation | 1 |
| S4-3 | Alembic migration baseline check in CI | 1 |
| S4-4 | Production deploy runbook | 2 |
| S4-5 | End-to-end smoke test on staging | 2 |

---

## Open questions (must resolve before Sprint 2)

1. **Budget enforcement**: When `cost_budget_cents` is exceeded mid-job, does the worker hard-stop remaining renders or soft-warn and continue? This affects the render worker loop design.
2. **AI provider for Director Agent**: Anthropic key is in `.env.example` but the director agent adapter needs to be confirmed as Claude-backed (check `director_agent_adapter.py`).
3. **R2 vs local storage for SRT files**: The transcription SRT files are currently written to a temp path. In production (Modal), the worker filesystem is ephemeral — SRTs must be uploaded to R2 before the render step reads them, or the render and transcription must happen in the same process.
4. **Font availability on Modal image**: The font probe expects system fonts. The Modal Docker image (Debian slim) has no GUI fonts. Must `apt-get install fonts-liberation` or bundle a TTF in the repo.
5. **Vercel vs Cloudflare Pages for Next.js**: Affects `outputFileTracingRoot` relevance and whether the next.config.ts change is even necessary.

---

## What the AURA plan contributed vs. what changed

| AURA concept | This project's equivalent | Decision |
|---|---|---|
| Streamlit Prompt Library tab | Brief Template Library in Next.js | ✅ Adopted, re-platformed |
| Ed25519 + C2PA-shaped manifest | Render artifact signing (provenance.py) | ✅ Adopted as Phase 3 |
| Plugin architecture (providers) | Renderer registry already exists | ✅ Renderer registry is the plugin system; expand it |
| Provider health-check | Worker health endpoint + queue depth | ✅ Adopted as P2-2 |
| Together/Replicate providers | Not applicable (Modal + Anthropic) | ❌ Not applicable |
| ~/.aura/prompt_library.db SQLite | Postgres `brief_templates` table | 🔄 Upgraded to existing DB |
| CI/pytest ≥ 90% | 85% services / 60% overall | ✅ Adopted, target adjusted |
| Dark mode / glassmorphism | Keep existing Next.js design system | ⏸ Deferred post-MVP |
