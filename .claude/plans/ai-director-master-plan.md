# AI Director — Master Implementation Plan
> Written from live codebase audit · June 2026  
> Current production readiness: **40%** → Target: **100%**

---

## Executive Summary

The codebase has an excellent foundation: strong schema design, real auth (Clerk JWT), 
solid CI, legal pages, and a cinematic UI. What's missing is the *live* layer — 
R2 wiring, webhook security, billing, export URLs, real worker dispatch, and 
4 frontend pages still showing fixture data. This plan closes every gap in 
priority order, adds the moat features that make the product hard to copy, 
and hardens the system for production deployment.

---

## Current State (Audit Snapshot)

| Layer | Real | Stubbed / TODO |
|-------|------|----------------|
| Auth (Clerk JWT + middleware) | ✅ | — |
| DB models + Alembic (0001→0006) | ✅ | — |
| Jobs router + RQ dispatch | ✅ | — |
| Director plans router | ✅ | — |
| Renders router (read-only) | ✅ | — |
| Brief templates CRUD | ✅ | — |
| Health + queue health | ✅ | — |
| Legal pages (Terms + GDPR) | ✅ | — |
| Landing page + pricing | ✅ | — |
| CI (test + alembic + build) | ✅ | — |
| Webhook signature verification | ❌ | Clerk + Stripe both TODO |
| R2 presign (real upload) | ❌ | Returns fake stub URL |
| Export presigned URL | ❌ | NotImplementedError |
| Billing portal + usage | ❌ | NotImplementedError + zeros |
| Rate limiting | ❌ | None |
| CORS (tightened) | ❌ | allow_methods=*, allow_headers=* |
| Frontend: clips page | ❌ | Fixture data |
| Frontend: director index | ❌ | Fixture redirect |
| Frontend: renders page | ❌ | Fixture data |
| Frontend: performance page | ❌ | Fixture data |
| Scene-analysis Modal worker | ❌ | TODO comment in modal_app.py |
| Director Agent (LLM) wiring | ❌ | Queue exists, worker missing |
| Stripe metered billing | ❌ | meter IDs not set |
| Provenance on export download | ❌ | Signing exists, not called on export |

---

## Sprint 5 — Security Hardening (Week 1, BLOCKING)
> Nothing ships until these are done. Unsigned webhooks are a free account-takeover vector.

### S5-1: Clerk webhook signature verification
**File:** `apps/api/src/api/routers/webhooks.py`  
- Install `svix` Python SDK (`uv add svix`)
- Verify `svix-id`, `svix-timestamp`, `svix-signature` headers using `CLERK_WEBHOOK_SECRET`
- On success: parse event type → `user.created` / `user.updated` / `user.deleted` → upsert/delete Tenant + User rows
- Return 400 on bad signature (never 200)
- Unit tests: valid payload passes, tampered payload 400s

### S5-2: Stripe webhook signature verification
**File:** `apps/api/src/api/routers/webhooks.py`  
- Use `stripe.WebhookSignature.verify_header()` with `STRIPE_WEBHOOK_SECRET`
- Handle events: `invoice.payment_succeeded` → mark subscription active, `invoice.payment_failed` → flag tenant, `customer.subscription.deleted` → downgrade
- Unit tests: valid Stripe event passes, replay attack (stale timestamp) 400s

### S5-3: Rate limiting middleware
**File:** `apps/api/src/api/main.py` + new `apps/api/src/api/middleware/rate_limit.py`  
- Install `slowapi` (`uv add slowapi`)
- Limits:
  - `POST /api/uploads/presign` → 10/min per tenant
  - `POST /api/jobs` → 20/min per tenant
  - `POST /api/director-plans` → 30/min per tenant
  - All others → 120/min per tenant
- Key function: extract tenant_id from Bearer token (no auth overhead — parse JWT claim only)
- Return `429` with `Retry-After` header

### S5-4: Tighten CORS
**File:** `apps/api/src/api/main.py`  
- `allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]`
- `allow_headers=["Authorization", "Content-Type", "X-Request-ID"]`
- `ALLOWED_ORIGINS` must be set in production env; startup_check adds it to WARN list

### S5-5: Security headers middleware
**File:** `apps/api/src/api/main.py`  
- Add `SecurityHeadersMiddleware` (custom, 20 lines):
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Permissions-Policy: camera=(), microphone=()`
- Next.js: add `headers()` config in `next.config.ts` with same set + `Content-Security-Policy`

### S5-6: Unit tests for all S5 items
- `tests/unit/test_webhooks.py`: 12 tests covering Clerk + Stripe happy/error paths
- `tests/unit/test_rate_limit.py`: 6 tests — under limit passes, over limit 429

---

## Sprint 6 — Core Pipeline Wiring (Week 2, REVENUE-BLOCKING)
> Users cannot actually upload or export without these.

### S6-1: R2 real presign
**File:** `apps/api/src/api/routers/uploads.py`  
- Install `boto3` (`uv add boto3`) — R2 is S3-compatible
- `_presign_r2(tenant_id, upload_id, filename, content_type) -> dict`
  - Endpoint: `https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com`
  - Key: `tenants/{tenant_id}/uploads/{upload_id}/{filename}`
  - Expiry: 900s (15 min)
  - Returns `{url, fields}` for multipart POST from browser
- Graceful fallback when R2 env vars absent (dev mode): return local-storage stub with warning log
- Unit tests: mock boto3 session, assert key shape

### S6-2: Upload complete + R2 head-check
**File:** `apps/api/src/api/routers/uploads.py`  
- On `POST /api/uploads/{id}/complete`: call `s3.head_object()` to verify file landed in R2
- Set `upload.r2_key`, `upload.size_bytes`, `upload.status = "ready"`
- If head fails → 422 with clear error (don't silently mark ready)

### S6-3: Export presigned download URL
**File:** `apps/api/src/api/routers/exports.py`  
- `GET /api/exports/{render_output_id}/url`
  - Lookup RenderOutput row, verify tenant ownership
  - Generate 1-hour presigned GET URL from R2
  - Attach provenance manifest as response header `X-Provenance-Manifest` (base64 JSON)
  - Log `UsageEvent(type="export_download", tenant_id, render_output_id)`
- Unit tests: tenant isolation (other tenant gets 403), expired URL regenerates

### S6-4: Frontend Phase 9.5 wiring — all 4 pages
Wire the 4 fixture-mode pages to real API data:

**`apps/web/app/app/clips/page.tsx`**  
- Accept `?jobId=<uuid>` query param
- Use `useJobView(jobId)` hook (already exists)
- Show empty-state with "Start a pipeline" CTA when no jobId

**`apps/web/app/app/director/page.tsx`**  
- Replace fixture redirect with real job selector (most recent job from `useRecentJobs()`)
- Redirect to `/app/director/{mostRecentJobId}`

**`apps/web/app/app/renders/page.tsx`**  
- Accept `?jobId=<uuid>` param
- Fetch from `/api/renders?job_id={jobId}` using `useRenders(jobId)` hook (new)

**`apps/web/app/app/performance/page.tsx`**  
- Accept `?jobId=<uuid>` param  
- Use `useJobView(jobId)` for engagement snapshots

**New hook:** `apps/web/hooks/useRenders.ts`  
- Fetches `GET /api/renders?job_id=<id>`, polls every 5s while any render is `running`

### S6-5: Frontend API URL wiring
**File:** `apps/web/.env.example`  
- Document `NEXT_PUBLIC_API_URL=http://localhost:8000` as required for real data
- Add env check in `apps/web/lib/api/runtime.ts`: warn in console when running fixture mode

---

## Sprint 7 — Billing & Monetization (Week 3)
> Without billing, the Free tier is the only tier.

### S7-1: Stripe customer lifecycle
**File:** `apps/api/src/api/services/billing.py` (new)  
- `create_stripe_customer(tenant_id, email, name) -> str` — called from Clerk webhook on org.created
- `get_or_create_subscription(tenant_id, price_id) -> Subscription`
- `record_usage_event(tenant_id, metric: Literal["match", "export", "asr_minute", "gpu_second"], quantity)`
  - Posts to Stripe Meters API for metered billing
  - Also writes `UsageEvent` row to Postgres for internal audit

### S7-2: Billing router
**File:** `apps/api/src/api/routers/billing.py`  
- `GET /api/billing/portal` → Create Stripe Customer Portal session, return `{url}`
- `GET /api/billing/usage` → Query `UsageEvent` table for current period, return real counts
- `GET /api/billing/subscription` → Return plan name, status, current period end, usage vs limit

### S7-3: Usage gates
**File:** `apps/api/src/api/services/limits.py` (new)  
- `check_match_quota(tenant_id)` → raises `402 Payment Required` if matches this month ≥ plan limit
  - Starter: 5, Pro: 50, Studio: unlimited
- Called from `POST /api/jobs` before queue dispatch
- Called from `POST /api/uploads/presign` as early gate

### S7-4: Billing UI (frontend)
**File:** `apps/web/app/app/settings/billing/page.tsx` (new)  
- Current plan card (name, renewal date, usage bar)
- "Manage billing" button → opens Stripe portal in new tab
- Usage breakdown: matches used / limit, exports, ASR minutes
- Upgrade CTA for Starter users

### S7-5: Sidebar: add Settings
**File:** `apps/web/components/layout/Sidebar.tsx`  
- Add `{ href: "/app/settings/billing", label: "Settings", icon: Settings }` to NAV

---

## Sprint 8 — AI Workers (Week 4, CORE PRODUCT VALUE)
> The intelligence layer is the entire product moat.

### S8-1: Scene-analysis Modal worker
**File:** `apps/api/modal_app.py` (line 68 TODO)  
- Implement `run_scene_analysis(payload)`:
  - Download source file from R2 to `/tmp/`
  - Run OmegaClips FI-1→FI-13 pipeline (`packages/intel`)
  - Write `ClipCandidate` rows to DB with raw FI scores
  - Update `Job.status = "candidates_ready"`
  - Push `JobEvent(type="analysis_complete")` for frontend polling
- `drain_cv_queue()` cron: same pattern as render queue drain

### S8-2: Director Agent (LLM worker)
**File:** `apps/api/workers/director_agent_worker.py` (new)  
- `execute_director_agent(payload) -> dict`
  - Fetch Job + ClipCandidates from DB
  - Call Anthropic `claude-sonnet-4-6` with structured tool use:
    - Tool: `build_director_plan(clips, brief)` → returns DirectorPlan JSON
    - System prompt: cinematic sports editor persona, respects trust-gradient cap ±0.15
  - Persist `DirectorPlan` row
  - Enqueue render jobs for each selected clip
- Register on `q:llm` queue in `jobs.py`

### S8-3: End-to-end pipeline auto-trigger
**File:** `apps/api/src/api/routers/jobs.py`  
- After `POST /api/jobs` enqueues CV analysis, the CV worker on completion auto-enqueues LLM director agent
- LLM worker on completion auto-enqueues render worker
- Each stage emits a `JobEvent` row — frontend `useJobView` polls these for live timeline

### S8-4: Worker tests
- `tests/unit/test_director_agent_worker.py`: mock Anthropic call, assert DirectorPlan shape
- `tests/integration/test_pipeline.py`: extend existing scaffold with stage-transition assertions

---

## Sprint 9 — Moat Features (Week 5, HARD TO COPY)
> These are the features that justify the price and defend the product.

### S9-1: Provenance on every export
**File:** `apps/api/src/api/routers/exports.py`  
- On each export download, call `ProvSigner.from_env().sign_manifest(assertion)`
- Embed signed manifest in MP4 metadata via `ffmpeg -metadata` XMP tag
- Store `ProvenanceManifest` JSON in R2 alongside clip: `…/{render_output_id}.c2pa.json`
- Return `X-Provenance-Key-Id` and `X-Provenance-Manifest-Url` response headers

### S9-2: Brief Template sharing & marketplace
**File:** `apps/api/src/api/routers/brief_templates.py` + new migration `0007`  
- Add `is_public: bool = False` and `use_count: int = 0` to BriefTemplate
- `GET /api/brief-templates/marketplace` — list public templates, ordered by use_count
- `POST /api/brief-templates/{id}/fork` — copy public template to own tenant
- Frontend: add Marketplace tab to `/app/templates` page

### S9-3: Clip performance feedback loop
**File:** `apps/api/src/api/routers/engagement.py` (new)  
- `POST /api/engagement` — ingest view_count, like_count, share_count per clip
  - Validates cap: engagement delta capped at ±0.15 on final score (trust-gradient rule)
  - Writes `EngagementEvent` row
  - Updates `ClipCandidate.engagement_score` asynchronously via RQ task
- Frontend: `apps/web/app/app/performance/page.tsx` gains "Sync engagement" button

### S9-4: Structured audit trail (admin view)
**File:** `apps/web/app/app/settings/audit/page.tsx` (new)  
- Table of all `JobEvent` rows for the tenant
- Columns: timestamp, event type, actor (system / user), affected entity
- Export as CSV
- Read-only; only visible to org admin role (Clerk `org:admin` permission check)

### S9-5: Deterministic replay
**File:** `apps/api/src/api/routers/jobs.py`  
- `POST /api/jobs/{id}/replay` — re-run the full pipeline with the same source file and brief
  - Creates new Job row, copies DirectorPlan brief as starting point
  - Useful for A/B testing brief templates
- Frontend: "Replay" button on job detail page

---

## Sprint 10 — Production Polish (Week 6, DEPLOY QUALITY)

### S10-1: Structured request IDs
**File:** `apps/api/src/api/main.py`  
- `RequestIDMiddleware`: inject `X-Request-ID` (UUID) on every request/response
- Log request_id in every log line (logfire context var)
- Frontend: include `X-Request-ID` in all fetch calls; log to browser console in dev

### S10-2: API versioning
**File:** `apps/api/src/api/main.py`  
- Prefix all routes with `/api/v1/` (backward-compat alias for `/api/`)
- Add `API-Version: 1` response header
- Document versioning policy in DEPLOY.md

### S10-3: Database connection pooling
**File:** `apps/api/src/api/database.py`  
- Set `pool_size=10, max_overflow=20, pool_pre_ping=True`
- Neon requires `?sslmode=require` in DATABASE_URL — add to startup_check WARN
- Add `/health/db` endpoint: SELECT 1, return latency_ms

### S10-4: Next.js production hardening
**File:** `apps/web/next.config.ts`  
- Add `Content-Security-Policy` header via `headers()` config
- Enable `output: "standalone"` for Docker-friendly build
- Add `compress: true` (gzip)
- Set `poweredByHeader: false`

### S10-5: Sentry source maps
**File:** `apps/web/next.config.ts` + `apps/api/pyproject.toml`  
- Frontend: `@sentry/nextjs` with `withSentryConfig()` wrapper; upload source maps on build
- Backend: `sentry_sdk.init()` already gated on `SENTRY_DSN`; add `release` tag from `GIT_SHA` env

### S10-6: Lighthouse CI
**File:** `.github/workflows/ci.yml`  
- Add `web-lighthouse` job: build Next.js, serve with `next start`, run `lhci autorun`
- Assert: Performance ≥ 85, Accessibility ≥ 90, Best Practices ≥ 90
- Blocks merge if scores regress

### S10-7: Seed script for staging
**File:** `apps/api/scripts/seed_staging.py` (new)  
- Creates 1 demo tenant + user
- Uploads a 30s test clip
- Runs full pipeline (fixtures mode for CV, real FFmpeg render)
- Verifies `/health`, `/health/queue`, `/api/jobs` return expected shapes
- Called from deploy runbook after `alembic upgrade head`

---

## Moat Summary (What Makes This Hard to Copy)

| Moat Layer | Implementation | Why Hard to Copy |
|------------|----------------|------------------|
| **OmegaClips FI-1→13** | Vendored `packages/intel` submodule | Private engine; 13 football-specific signals built over years |
| **Trust-gradient cap** | ±0.15 engagement gate, 0.30 threshold | Principled ML design; copycats drift to pure engagement optimisation and degrade |
| **C2PA provenance** | Ed25519 per-clip signing + R2 sidecar | Chain of custody from source to export; broadcaster requirement |
| **Brief Template marketplace** | Tenant-sharable presets + fork API | Network effect: every user's templates make the product better for all |
| **Deterministic replay** | Same brief + source → reproducible output | Audit requirement for rights holders; hard to bolt on later |
| **Structured audit trail** | Every pipeline decision logged | Enterprise compliance requirement; not viable with a simple SaaS clone |
| **Feedback cap discipline** | Engagement assists, never overrides | Protects editorial integrity; requires deliberate architecture to maintain |

---

## Security Hardening Checklist

| Control | Sprint | Status |
|---------|--------|--------|
| Clerk webhook Svix verification | S5-1 | TODO |
| Stripe webhook signature | S5-2 | TODO |
| Rate limiting (slowapi) | S5-3 | TODO |
| CORS tightened | S5-4 | TODO |
| Security headers (API + web) | S5-5 | TODO |
| R2 presign (no client-side secrets) | S6-1 | TODO |
| Usage gates (quota enforcement) | S7-3 | TODO |
| Provenance on every export | S9-1 | TODO |
| Tenant isolation (all queries scoped) | ✅ Done | — |
| JWT RS256 verification | ✅ Done | — |
| Pydantic extra=forbid schemas | ✅ Done | — |
| Startup env validation | ✅ Done | — |
| GDPR DSR process | ✅ Done | — |
| Ed25519 signing infrastructure | ✅ Done | — |

---

## Ticket Count by Sprint

| Sprint | Tickets | Theme |
|--------|---------|-------|
| S5 | 6 | Security hardening |
| S6 | 5 | Core pipeline wiring |
| S7 | 5 | Billing & monetization |
| S8 | 4 | AI workers |
| S9 | 5 | Moat features |
| S10 | 7 | Production polish |
| **Total** | **32** | |

---

## Definition of Done

A sprint is complete when:
1. All unit tests pass (`uv run pytest tests/unit/`)
2. `pnpm tsc --noEmit` exits 0
3. `pnpm build` exits 0  
4. No new `TODO` / `NotImplementedError` / fixture-mode fallbacks introduced
5. DEPLOY.md updated if any new env var added
6. Smoke tests pass against staging (`STAGING_API_URL=… pytest tests/smoke/`)
