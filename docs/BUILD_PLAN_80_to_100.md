# AI Director — Build Plan: 60% → 80% → 100%

**Built:** July 2026  
**Current baseline:** ~60% deployment readiness (verified by codebase audit)  
**Target 1:** 80% — production-safe MVP with complete pipeline (weeks 1-6)  
**Target 2:** 100% — world-class platform with unassailable moats (weeks 7-14)  
**Mindset:** SpaceX first-principles engineering × Starlink operational rigor

---

## Table of Contents

1. [The SpaceX/Starlink Mindset Applied to This Product](#1-the-mindset)
2. [Where We Stand Today (60% Baseline)](#2-current-baseline)
3. [The Plan: 60% → 80% — Production-Ready MVP](#3-plan-60-to-80)
   - [Sprint 1: Pipeline First — Make It Real](#sprint-1-pipeline-first)
   - [Sprint 2: Failsafe Foundation](#sprint-2-failsafe-foundation)
   - [Sprint 3: Revenue-Ready](#sprint-3-revenue-ready)
   - [Sprint 4: Operational Hardening](#sprint-4-operational-hardening)
4. [At 80%: What the Product Does & What Users Experience](#4-at-80-percent)
5. [The Plan: 80% → 100% — Unassailable Moat](#5-plan-80-to-100)
   - [Sprint 5: Intelligence Moat](#sprint-5-intelligence-moat)
   - [Sprint 6: Trust & Compliance Moat](#sprint-6-trust-compliance-moat)
   - [Sprint 7: Ecosystem Moat](#sprint-7-ecosystem-moat)
   - [Sprint 8: Autonomous Ops Moat](#sprint-8-autonomous-ops-moat)
6. [At 100%: The Unicorn Product](#6-at-100-percent)
7. [Engineering Principles Embedded at All Levels](#7-engineering-principles)
8. [Risk Register & Mitigations](#8-risk-register)
9. [Definition of Done for Each Gate](#9-dod)

---

## 1. The SpaceX/Starlink Mindset Applied to This Product

This plan is not a conventional software roadmap. It is built on first-principles engineering patterns proven at SpaceX and Starlink — adapted for a solo/small-team SaaS.

### The Core Loop (adapted from SpaceX's "The Algorithm")

```
┌─────────────────────────────────────────────────────────────┐
│  1. QUESTION EVERY REQUIREMENT                              │
│     → "What actual user outcome does this serve?"           │
│     → Delete requirements, not just code                    │
├─────────────────────────────────────────────────────────────┤
│  2. DELETE THE PART/PROCESS                                 │
│     → Every dependency, abstraction, config = failure mode  │
│     → If removing it doesn't break the user promise, kill it│
├─────────────────────────────────────────────────────────────┤
│  3. SIMPLIFY & OPTIMIZE                                     │
│     → Now that cruft is gone, make remaining pieces simpler │
├─────────────────────────────────────────────────────────────┤
│  4. GO FASTER                                               │
│     → Reduce cycle time. Ship smaller batches more often    │
├─────────────────────────────────────────────────────────────┤
│  5. AUTOMATE (now that the process is correct)              │
│     → Never automate a broken process                       │
└─────────────────────────────────────────────────────────────┘
```

### The "Idiot Index" for Every Decision

For every tool, dependency, and service, ask:

```
cost of current solution ($/month + maintenance hours)
────────────────────────────────────────────────────────
cost of simplest possible solution (raw compute + storage)
```

If > 3x, you are paying for process, not value. The codebase already has examples of doing this right (e.g., `r2.py` with dual local/R2 mode instead of an expensive CDN abstraction).

### Starlink-Inspired Deployment Philosophy

| Starlink Pattern | SaaS Equivalent |
|---|---|
| A/B boot partitions | Docker image tags + canary deploy |
| Canary in orbit | Deploy to 1 instance first, monitor, then roll |
| Cell-by-cell activation | Tenant-by-tenant rollout (region, plan tier) |
| Self-healing satellite mesh | Auto-scaling groups + health checks |
| Telemetry-driven decisions | Prometheus + Grafana on 3 golden signals |
| Over-the-air updates | Feature flags + progressive delivery |

---

## 2. Where We Stand Today (60% Baseline)

### What's Real (✅ — ships with zero additional work)

| Layer | What works |
|---|---|
| **Auth** | Clerk JWT RS256 verification, org-scoped tenant isolation, FastAPI DI dependency pattern |
| **Data** | 7 clean Alembic migrations, SQLAlchemy models with indexes/foreign keys/JSON columns, pool_pre_ping, pool_size=10 |
| **API core** | 13 routers, request ID middleware, security headers, CORS hardened, rate limiting, startup env validation |
| **Health** | `/health`, `/health/db` (SELECT 1), `/health/queue` (Redis depth) |
| **Storage** | R2 dual-mode (production/local), presign_put/signed_get_url/head_object/put_local_file/parse_storage_uri |
| **Billing** | Customer lifecycle, portal sessions, subscription status, quota enforcement (402), usage metering stub |
| **Provenance** | Ed25519 signer + C2PA-shaped manifest schema, sidecar upload, verification method |
| **Webhooks** | Clerk (Svix) + Stripe signature verification, tenant/user upsert |
| **Frontend** | Landing page with pricing, Clerk auth, terms/privacy, design system, upload queue, polling transport, state machines |
| **CI** | 3 GitHub Actions jobs (api-test, alembic-check, web-build) |
| **Docs** | README, DEPLOY.md, dev env guide, proof-of-work documents for all phases |
| **Intel adapters** | scene_analysis_adapter (fixture path), clip_ranking_adapter (fixture path), director_agent_adapter, ranking_feedback_adapter, render_plan_adapter (FFmpeg), renderer_registry |
| **Worker scaffolds** | Modal app with cron bridges, drain queues, scene analysis + render + ranking + engagement + export workers |

### What's Broken or Stubbed (❌ — blocks production use)

| # | Issue | File(s) | Impact |
|---|---|---|---|
| B1 | 2 Modal workers raise `NotImplementedError` | `director.py:25`, `render_worker.py:39`, `scene_analysis_worker.py`, `clip_ranking_worker.py`, `engagement_worker.py`, `ranking_feedback_worker.py` | **Pipeline cannot complete.** Users upload → job created → queued → ∞ |
| B2 | 3 frontend pages depend on complete pipeline data | `clips/page.tsx`, `renders/page.tsx`, `performance/page.tsx` | All show "no data" because pipeline never finishes |
| B3 | `RENDER_MANIFEST_VERSION` still `"1"` | `render_manifest.py:35` | Schema drift — version guard in CI will catch this if bumped |
| B4 | `engagement.py` double-clamping — `clamped` flag always `False` | `engagement.py:36-37, 75-76` | Dead code path, breaks trust-gradient audit trail |
| B5 | `omega_client.py` uses fragile `parents[6]` path | `omega_client.py:11` | Breaks if directory structure changes |
| B6 | `render_plan_adapter.py` has no `static` renderer path | `render_plan_adapter.py` | Registry declares `static` but adapter can't handle it |
| B7 | `render_plan_adapter.py` FFmpeg subprocess timeout unhandled | `render_plan_adapter.py:118-123` | FFmpeg hang → unhandled exception → 500 |
| B8 | `export_worker.py` uses `.scalar_one()` with no guard | `export_worker.py:43,46` | Missing rows → `NoResultFound` → 500 |
| B9 | `engagement_worker.py` fetches Job by most-recent, not by job_id | `engagement_worker.py:51-55` | Wrong job used for usage events in multi-job tenants |
| B10 | No seed/bootstrap data for new tenants | missing | Every tenant sees empty states |
| B11 | Stripe meter IDs not populated | `.env.example` | Metered billing is dead code |
| B12 | No integration tests | missing | Cannot verify pipeline end-to-end |
| B13 | No Sentry source maps for frontend | `next.config.ts` | Unreadable error stacks in production |
| B14 | No WebSocket endpoint | missing | Polling works but adds latency |
| B15 | No API versioning prefix | `main.py` | Routes at `/api/` not `/api/v1/` |
| B16 | No Lighthouse CI | CI | Performance regression goes undetected |
| B17 | `transcribe.py`, `clip_format.py`, `viral_title.py` not wired to API | services/ | Implemented but never called from any endpoint |

---

## 3. Plan: 60% → 80% — Production-Ready MVP (6 weeks)

### Sprint 1: Pipeline First — Make It Real (Week 1)

**Goal:** The pipeline completes end-to-end. A user uploads a file, and clips come out the other side.

#### S1-1: Un-stub the Modal workers (CRITICAL — BLOCKING)

This is the single highest-leverage change in the entire plan. Currently 6 worker entrypoints raise `NotImplementedError`.

**What to do:**

Take the already-working `_run_four_vertical_clips.py` (which is a proven, standalone blueprint of the correct pipeline) and port its logic into the real workers.

For each worker, the pattern is identical:
1. Pop payload from RQ (already have drain cron)
2. Read inputs from DB
3. Call the already-working adapter function
4. Persist results
5. Enqueue next stage

| Worker | Adapter exists? | Work needed |
|---|---|---|
| `scene_analysis_worker.analyze_video()` | ✅ `scene_analysis_adapter.py` | Remove `NotImplementedError`, call adapter with DB-loaded inputs, persist `Scene` + `ClipCandidate` rows, enqueue `q:llm` |
| `director_worker.build_director_plan()` | ✅ `director_plan_builder.py` + `director_agent_adapter.py` | Remove `NotImplementedError`, load candidates from DB, call builder, optionally enrich via Anthropic, persist `DirectorPlan`, enqueue `q:render-cpu` |
| `render_worker.render_one()` | ✅ `render_plan_adapter.render_clip()` + `render_manifest_builder.build_manifests()` | Remove `NotImplementedError`, load `DirectorPlan`, build manifests, call render_clip, persist `RenderOutput`, enqueue `q:export` |
| `export_worker.evaluate_export_now()` | ✅ `export_artifact_builder.py` | Remove `NotImplementedError`, call builder, upload to R2, persist |
| `clip_ranking_worker.rank_clip_candidates()` | ✅ `clip_ranking_adapter.py` | Already has fixture path — add DB read path |
| `ranking_feedback_worker.apply_ranking_feedback_for_job()` | ✅ `ranking_feedback_adapter.py` | Already has fixture path — add DB read path |

**Files to modify:** 6 worker files  
**Estimated effort:** 2 days  
**First-principles check:** *Why does this exist?* Answer: It's the core product. Delete nothing here.

#### S1-2: Wire title + subtitle overlay (UNLOCKS FRONTEND VALUE)

**What:** The `render_manifest_builder._build_one()` already accepts optional `srt_output_dir` for transcription. The caller never passes it. Wire it.

**Files:** `render_manifest_builder.py`, `render_worker.py`  
**Effort:** 4 hours  
**First-principles check:** *Should this be synchronous?* No — transcription is slow. Make it async within the worker (run in a thread pool).

#### S1-3: Fix 6 bugfixes from the audit

| ID | Fix | Effort |
|---|---|---|
| B3 | Bump `RENDER_MANIFEST_VERSION` to `"2"` with schema migration comment | 15 min |
| B4 | Remove double-clamping in `engagement.py` — keep only `@field_validator` | 15 min |
| B5 | Replace `parents[6]` with project-root-relative path using `pathlib` | 30 min |
| B7 | Wrap FFmpeg subprocess call in try/except with structured error | 30 min |
| B8 | Replace `.scalar_one()` with `.scalar_one_or_none()` + 404 in export_worker | 30 min |
| B9 | Fix engagement worker to fetch Job by actual job_id (not most-recent) | 30 min |

**Total effort:** 2.5 hours  
**First-principles check:** Each of these is a latent production crash. Fix them before they trigger at 3am.

#### S1-4: Create integration test for the full pipeline

**What:** Promote `_run_four_vertical_clips.py` → `tests/integration/test_render_pipeline.py`. Gate behind `pytest.mark.integration` (skipped unless `SOURCE_VIDEO` env var is set). This is your **pre-flight abort check**: if this test fails, do not deploy.

**Files:** `tests/integration/test_render_pipeline.py` (new)  
**Effort:** 3 hours  
**SpaceX pattern:** *Deploy to test* — this test IS your engine test stand. It must run before every deploy.

#### Sprint 1 Deliverables:

```
✅ Pipeline completes end-to-end (upload → clips → render → export)
✅ 6 production bugs fixed
✅ Integration test validates the full pipeline
✅ Title + subtitle overlays on rendered clips
```

---

### Sprint 2: Failsafe Foundation (Week 2)

**Goal:** The product is reliable. Every external dependency has a fallback. Deployments are safe.

#### S2-1: Graceful degradation for every external dependency

Following Netflix/Starlink: *assume everything fails and build for it.*

| Dependency | Failure mode | Fallback | Implementation |
|---|---|---|---|
| Redis | Down | In-process memory queue | Wrap `queue_for()` in try/except → `InMemoryQueue` (list + threading) |
| Postgres | Down | Serve from cache | Cache recent JobView results in memory (Redis was the cache — in-process fallback with TTL) |
| R2 | Down | Local storage mirror | Already implemented in `r2.py` — verify it works end-to-end |
| Stripe API | Down | Allow operation, flag for review | Already partially done in `billing.py` — add `degraded` flag to health endpoint |
| Anthropic API | Down | Deterministic fallback | Already implemented in `modal_app.py:_run_director_agent()` — verify coverage |
| FFmpeg | Missing | Return structured error, transition job to FAILED | Add startup check for `ffmpeg -version` |

**Effort:** 1 day  
**SpaceX pattern:** *Redundancy is not optional.* Starlink satellites survive losing multiple RF beams. Your SaaS should survive losing any single dependency.

#### S2-2: Deploy safety — canary + auto-rollback

**Implementation for a solo developer:**

```
1. Two instances behind load balancer (already in docker-compose topology)
2. Deploy to instance 1 → wait 5 min
3. Monitor: error rate, p95 latency, health check pass rate
4. If degraded → instance 2 stays live, roll back instance 1
5. If healthy → deploy to instance 2
```

**Tools:** Use `docker-compose` with health checks + a simple bash deploy script. Don't add Kubernetes yet — that's process overhead that fails SpaceX's Algorithm step 2 (delete the part).

**Effort:** 4 hours  
**First-principles check:** *Do we need K8s?* No — 2 Docker instances + LB is simpler, cheaper, and more reliable for a solo team.

#### S2-3: Feature flags for every risky change

**What:** Install Flipt (single binary, zero deps, self-hosted) or use a simple JSON config file + environment variables.

**Minimum flags needed:**
```
pipeline.use_modal_workers (bool)    — toggle between local RQ + Modal
pipeline.enable_llm_enrichment (bool) — toggle Anthropic Director Agent
billing.enforce_quotas (bool)         — toggle quota checking
frontend.show_fixture_data (bool)     — toggle mock data on frontend pages
```

**Effort:** 3 hours  
**Starlink pattern:** Every satellite can be reconfigured from ground. Every feature in your SaaS should be toggleable from a config file or env var.

#### S2-4: WebSocket endpoint for real-time pipeline progress

**What:** The frontend's `WebSocketTransport` class is ready. Build the backend endpoint:
- `WS /api/jobs/{id}/events` — emits `JobEventsView` on every state transition
- Subscribe via Postgres LISTEN/NOTIFY or Redis Pub/Sub

**Effort:** 4 hours  
**First-principles check:** *Do users need real-time updates?* Yes — a 4-minute pipeline with polling at 4s intervals means 60 useless requests. WebSocket is the right tool for streaming progress.

#### Sprint 2 Deliverables:

```
✅ Every external dependency has a graceful fallback
✅ Deploy script with canary logic
✅ Feature flags for risky features
✅ WebSocket endpoint for real-time pipeline updates
✅ No single point of failure can crash the entire app
```

---

### Sprint 3: Revenue-Ready (Week 3)

**Goal:** You can charge real money. Billing works end-to-end. Usage tracking is accurate.

#### S3-1: Real Stripe metered billing

**What:** The Stripe Meter IDs (`STRIPE_METER_ASR_MINUTES`, `STRIPE_METER_GPU_SECONDS`, `STRIPE_METER_EXPORT_COUNT`) are in `.env.example` but never wired. Create the Stripe meters in the Stripe dashboard, then wire `record_meter_event()` to call them at the right pipeline stages.

**Where to call metering:**

| Pipeline stage | Meter | Quantity |
|---|---|---|
| Scene analysis complete | `gpu_second` | Actual GPU seconds from worker |
| Render complete | `gpu_second` | Actual GPU seconds |
| Export created | `export` | 1 per export |

**Files:** `apps/api/src/api/services/billing.py:record_meter_event()`  
**Effort:** 3 hours  
**First-principles check:** *Are metered customers better than flat-fee?* For this product: yes. Per-match pricing aligns cost with value. Start with tiered (Starter=5, Pro=50, Studio=unlimited) + metered overage.

#### S3-2: Billing UI page

**Frontend page at `/app/settings/billing`:**
- Current plan card with name, renewal date, usage bar (matches used / limit)
- "Manage billing" button → Stripe Customer Portal
- Usage breakdown: matches used, exports, ASR minutes
- Upgrade CTA for Starter users

**Effort:** 4 hours  
**SpaceX pattern:** *The customer portal is your launch pad.* Make it simple, functional, and reliable. No fancy animations — just clear information and one action button.

#### S3-3: Usage gates enforced in production

**What:** `check_match_quota()` exists. Verify it's called in:
- `POST /api/jobs` (already done ✅)
- `POST /api/uploads/presign` (✅ already done)

Add:
- `GET /api/billing/usage` returns real counts (already done ✅ — verify accuracy)
- Return a human-readable 402 error when quota is exceeded (✅ already done)

**Effort:** 2 hours (mostly testing/verifying)  
**First-principles check:** *Do all tiers need gating?* No — Studio/unlimited should skip the check entirely (already done via `limit=None`).

#### S3-4: Fix remaining billing gaps

- Add Stripe price IDs to settings (for `_price_to_plan`)
- Wire `customer.subscription.updated` webhook handler to update tenant plan in DB
- Wire `customer.subscription.deleted` to downgrade tenant to Starter

**Effort:** 3 hours

#### Sprint 3 Deliverables:

```
✅ Real Stripe metered billing active
✅ Billing UI page with usage dashboard
✅ Usage gates enforced at every entry point
✅ Subscription lifecycle handled end-to-end
✅ You can charge real money
```

---

### Sprint 4: Operational Hardening (Week 4)

**Goal:** The product is observable, deployable, and maintainable by a solo operator.

#### S4-1: Observability — 3 golden signals on every endpoint

**What:** Prometheus metrics for every FastAPI endpoint:
- **Error rate** (5xx / total)
- **Latency** (p50/p95/p99)
- **Request rate** (requests/second)

**Implementation:** Use `prometheus-fastapi-instrumentator` (adds metrics with 3 lines of code). Export at `/metrics`.

Add structured logging (Logfire already in deps — wire it to every service):

| Service | What to log |
|---|---|
| All routers | Request ID, method, path, status, duration |
| `r2.py` | Key, operation (PUT/GET/HEAD), bytes, duration |
| `billing.py` | Customer ID, operation, Stripe response |
| All workers | Job ID, stage, duration, result |
| `render_plan_adapter.py` | Manifest version, output path, duration, success/failure |

**Files:** `main.py` (add metrics), every service file (add structured logging)  
**Effort:** 1 day  
**SpaceX pattern:** *Telemetry is not optional.* You cannot improve what you don't measure. Start with the 3 golden signals and iterate.

#### S4-2: Sentry source maps + release tracking

**Frontend:**
```typescript
// apps/web/next.config.ts
import { withSentryConfig } from "@sentry/nextjs";
```

**Backend:**
```python
# Already wired in main.py — add release tag
sentry_sdk.init(
    dsn=settings.sentry_dsn,
    release=os.environ.get("GIT_SHA", "dev"),
    traces_sample_rate=0.1,
)
```

**Effort:** 2 hours  
**First-principles check:** *Can you debug a production error without source maps?* No. This is infrastructure, not feature work.

#### S4-3: Seed script for staging/demo

**What:** `scripts/seed_staging.py` — creates 1 demo tenant, uploads a 30s test clip, runs full pipeline (fixtures mode for CV, real FFmpeg render), verifies `/health` and `/api/jobs` return expected shapes.

Called from deploy runbook after `alembic upgrade head`.

**Effort:** 3 hours  
**Starlink pattern:** *Every satellite deployment is validated against a known-good configuration.* Your seed script is that validation.

#### S4-4: API versioning + backward compat

**What:** Prefix all routes with `/api/v1/`. Add backward-compatible redirect from `/api/`.

```python
# In main.py: add router with prefix /api/v1 and keep existing /api
# Add redirect middleware for /api/* → /api/v1/*
```

**Effort:** 2 hours  
**First-principles check:** *Do you need versioning at 80%?* Yes — the frontend already uses typed API routes. Versioning prevents breaking changes when you add v2 endpoints.

#### S4-5: Lighthouse CI for performance regression

**What:** Add a GitHub Actions job that runs Lighthouse against the landing page + app shell, asserting Performance ≥ 85, Accessibility ≥ 90, Best Practices ≥ 90.

**Effort:** 2 hours

#### Sprint 4 Deliverables:

```
✅ Prometheus metrics on all endpoints (error rate, latency, request rate)
✅ Structured logging in every service
✅ Sentry source maps for frontend + backend
✅ Seed script for staging validation
✅ API versioning prefix
✅ Lighthouse CI blocks performance regressions
✅ Solo operator can deploy, monitor, and debug from one dashboard
```

---

### Sprint 4.5: Polish & Edge Cases (Week 5)

**Goal:** The product feels finished. Edge cases are handled. Empty states are informative.

#### S4.5-1: Frontend empty states for all pipeline stages

The 3 "no data" pages (clips, renders, performance) already have basic empty states. Enhance them:

- **Clips page:** Show explanatory illustration + "Upload a match" CTA
- **Renders page:** Show pipeline progress (how far along is the current job)
- **Performance page:** Show "Complete a pipeline to see engagement stats" with animated preview
- **Director page:** Show job selector with most recent jobs, not just the first one

**Effort:** 1 day

#### S4.5-2: Handle all error states gracefully

- Upload fails → retry UI with countdown
- Pipeline fails → show which stage failed, with error message and "Retry" button  
- Billing error → show "Payment failed" with "Update billing" link
- Network offline → offline indicator with retry

**Effort:** 1 day

#### S4.5-3: Rate limit feedback

The API already returns 429 with `Retry-After` header. Frontend should:
- Catch 429 responses
- Show a toast: "Too many requests. Try again in X seconds."
- Disable submit buttons until cooldown expires

**Effort:** 4 hours

#### Sprint 4.5 Deliverables:

```
✅ Every page has a useful empty state
✅ Every failure has a clear error message + recovery path
✅ Rate limits are communicated to the user
✅ Product feels finished, not like a beta
```

---

## 4. At 80%: What the Product Does & What Users Experience

### User Story: First Visit (Marketing Site)

A content creator discovers AI Director. They land on the cinematic homepage, see the 3-tier pricing (Starter free, Pro $49/mo, Studio $179/mo), and click "Start free."

### User Story: First Upload

1. User signs in via Clerk (Google/GitHub/Email). **Time: 10 seconds.**
2. Redirected to `/app/upload`. The Upload Studio shows a drag-and-drop zone with platform targets (YouTube Shorts, TikTok, Instagram Reels).
3. User drops a 90-minute football match MP4. **Upload via presigned R2 URL. Time: ~3-5 minutes for 3GB.**
4. Upload progress bar shows 0% → 100%. User sees "78% · 2.4 GB of 3.1 GB" in real time.
5. Upload completes. System verifies via R2 HEAD check. Status: ✅ **ready**

### User Story: Pipeline in Flight

6. Next.js polls via WebSocket (or polling fallback). The Processing Timeline shows stages lighting up:
   - ✅ Upload (3.1 GB ingested)
   - 🔄 Analysis (FI-1→FI-13 running on Modal GPU)
   - ⏳ Ranking
   - ⏳ Directing
   - ⏳ Rendering
   - ⏳ Exporting

7. At Analysis stage, Modal worker runs scene analysis (OmegaClips FI-1→FI-13) on the video. Detects 8 goal events, 12 key passes, 5 saves. **Time: ~30 seconds.**
8. At Ranking stage, candidates are scored by confidence, quality, platform fit, virality, novelty. Top 6 are selected.
9. At Directing stage, Director Plan is built (deterministically or via Claude enrichment). Each selected candidate gets a RenderStyle, CaptionStyle, and Platform variant.
10. At Rendering stage, FFmpeg produces 3 variants per selected clip (9:16, 1:1, 16:9) with burned-in captions and title banner. **Time: ~2 minutes for 18 renders.**
11. At Exporting stage, each output gets an Ed25519 provenance manifest + content hash + export hash, stored alongside the clip in R2. **Time: ~10 seconds.**

**Total pipeline time: ~3 minutes.** User sees progress updates without refreshing.

### User Story: Reviewing Results

12. User navigates to `/app/clips?jobId=xxx`. The **Ranked Clips Board** shows 6 clips sorted by final rank score, each with:
    - Thumbnail (generated from first frame)
    - Score badge (e.g., 9.4)
    - Event type (Goal / Key pass / Save)
    - Timestamp (78:12)
    - Confidence + quality scores
    - Engagement boost indicator (if feedback has been applied)

13. Clicking a clip opens the **Director Review** workspace, showing:
    - The clip in context (surrounding play)
    - Director Plan rationale ("Selected for: climactic goal sequence, high crowd reaction, clean edit points")
    - Variant previews (9:16, 1:1, 16:9)
    - Download button with provenance headers (X-Provenance-Key-Id, X-Provenance-Manifest-Url)

### User Story: Exporting

14. User opens **Render & Export Center** (`/app/renders?jobId=xxx`). Summary cards show: 6 Render jobs, 18 Render outputs, 18 Export artifacts, total size.
15. Grouped by platform: YouTube Shorts (6 variants), TikTok (6 variants), Instagram Reels (6 variants).
16. Each variant shows: filename, status (completed), bytes, aspect ratio, cost ($0.06), content_hash, export_hash, storage_uri.
17. "Download" button generates a 1-hour presigned R2 URL. The HTTP response includes provenance headers.

### User Story: Billing & Limits

18. User checks **Settings → Billing**. Shows:
    - Plan: Starter (free)
    - Matches used: 2 of 5 this month
    - Exports: 6 of unlimited
    - "Upgrade to Pro for 50 matches" CTA
19. User hits the limit at match 6. `POST /api/jobs` returns HTTP 402 with message: "Monthly match limit reached (5/5 on starter plan). Upgrade to Pro for 50 matches/month or Studio for unlimited."
20. Frontend shows a modal: "You've hit your free limit" with Upgrade button → Stripe Customer Portal.

### What Users Expect at 80%

| Expectation | Met? | How |
|---|---|---|
| "I upload a match and get clips" | ✅ | Pipeline completes in ~3 min |
| "I can see progress without refreshing" | ✅ | WebSocket + Processing Timeline |
| "Clips are ranked by quality" | ✅ | Trust-gradient scoring |
| "I can export in platform formats" | ✅ | 9:16, 1:1, 16:9 per platform |
| "I can download with one click" | ✅ | Presigned R2 URL |
| "Billing works without talking to sales" | ✅ | Self-serve via Stripe portal |
| "If something breaks, the system tells me why" | ✅ | Error messages on every failure |
| "The product feels fast and reliable" | ⚠️ | Fast enough. Reliability improves in Sprints 5-8. |
| "The clips have captions and titles" | ✅ | Auto-generated from transcript |
| "I can trust the clips are authentic" | ⚠️ | Ed25519 provenance added. Full C2PA in later sprint. |

### Infrastructure at 80%

| Component | What runs it |
|---|---|
| **API** | 2 Docker containers behind nginx reverse proxy (or Railway/Fly.io) |
| **Database** | Neon Postgres (serverless, branching for staging) |
| **Queue** | Upstash Redis (serverless, TLS) |
| **Workers** | Modal (GPU for CV, CPU for render) |
| **Storage** | Cloudflare R2 (zero egress) |
| **Frontend** | Vercel (auto-deploy from main) |
| **Auth** | Clerk |
| **Billing** | Stripe |
| **Monitoring** | Prometheus (metrics) + Sentry (errors) + Logfire (structured logs) |
| **CI** | GitHub Actions (test, alembic check, Lighthouse, build) |

---

## 5. Plan: 80% → 100% — Unassailable Moat (Weeks 7-14)

The 80% product is good. The 100% product is *uncopyable*. Every feature in this phase is chosen because it creates a structural advantage that competitors cannot easily replicate.

The moats are layered:

```
                   ┌─────────────────────────────────────┐
                   │    5. Intelligence Moat              │
                   │  (FI-1→13, multi-sport, adaptive)    │
                   ├─────────────────────────────────────┤
                   │    6. Trust & Compliance Moat        │
                   │  (C2PA, audit trail, replay)         │
                   ├─────────────────────────────────────┤
                   │    7. Ecosystem Moat                 │
                   │  (templates, API, integrations)      │
                   ├─────────────────────────────────────┤
                   │    8. Autonomous Ops Moat            │
                   │  (self-healing, auto-scale, chaos)   │
                   └─────────────────────────────────────┘
```

---

### Sprint 5: Intelligence Moat (Weeks 7-8)

**Goal:** The AI gets better with every clip it processes. No competitor can match the intelligence depth without years of domain-specific investment.

#### S5-1: Trust-gradient feedback loop (production)

The architecture already has the components. Wire them in production:

1. Engagement delta (POST /api/engagement) → caps at ±0.15
2. Ranking feedback adapter applies capped adjustment
3. Next pipeline run uses adjusted scores

This creates a **self-improving system**: every user's feedback makes the system smarter for all users.

**Effort:** 2 days  
**Moat depth:** *High.* Trust-gradient with ±0.15 cap is principled ML design. Copycats who drift to pure engagement optimization will degrade their product quality over time.

#### S5-2: Multi-sport expansion

**Current state:** Only football (soccer) is implemented. 3 more sports are in the UI with "coming soon" badges (basketball, rugby, F1).

**What to build:**
1. Sport-specific intelligence profiles (adapt OmegaClips signals per sport)
2. Sport-specific render presets (aspect ratios, bitrates, safe zones)
3. Auto-detection of sport from video metadata (field dimensions, uniform colors, ball shape)

**Order of expansion:** Basketball → Rugby → F1 (by market size and technical feasibility)

**Effort per sport:** 3-5 days (mostly adapting OmegaClips signals)  
**Moat depth:** *Very High.* Each sport requires years of domain-specific CV training data. WSC Sports has 40+ sports after 10+ years. You need at least 5-6 for credible multi-sport positioning.

#### S5-3: Adaptive Director Agent — learn from user corrections

**What:** When a user manually adjusts a Director Plan (adds/removes clips, changes pacing, adjusts crop), the system records the delta and uses it to improve future plans.

**Implementation:**
1. Record every user override as a structured `UserCorrection` event
2. Periodically (weekly) run a batch job that correlates corrections with original Director Plan scores
3. Use correlations to adjust the deterministic ranking weights
4. Optional: use corrections as few-shot examples in the Claude enrichment prompt

**Effort:** 3 days  
**Moat depth:** *Very High.* This is a data network effect — the more users correct the system, the better it gets for everyone. WSC Sports doesn't do this (their system is one-way).

#### S5-4: Pipeline performance optimization

**What:** Profile the pipeline and optimize the slowest stages.

| Stage | Current estimated time | Target |
|---|---|---|
| Upload (3GB) | 3-5 min | 2-3 min (parallel chunk upload) |
| Scene analysis | 30s | 15s (GPU optimization) |
| Rendering (18 variants) | 2 min | 45s (parallel renders, GPU encoding) |
| Transcription | 20s | 10s (faster-whisper small model) |

**Key optimization:** Parallel render of variants. Current design renders 18 clips sequentially. Use Modal's `.map()` to render in parallel across 6-18 containers.

**Effort:** 2 days  
**First-principles check:** *Does a 3-minute pipeline need optimization?* For MVP: no. For competitive positioning: yes. "Match to clips in under 2 minutes" is a marketing claim that matters.

---

### Sprint 6: Trust & Compliance Moat (Weeks 9-10)

**Goal:** Every clip is self-authenticating. Broadcasters and rights holders *require* this level of provenance. No competitor offers it.

#### S6-1: Full C2PA-compliance

The codebase already has Ed25519 signing with C2PA-shaped manifests. But the spec is evolving. Upgrade to production C2PA v2.3:

1. Embed signed manifest as MP4 metadata (`-metadata` in FFmpeg)
2. Include DID (Decentralized Identifier) for creator identity
3. Register key with a public C2PA trust anchor
4. Add `X-Content-Credential` response header (per C2PA spec)

**Effort:** 3 days  
**Moat depth:** *Very High.* C2PA v2.3 (Jan 2026) extends to live/broadcast media. 6,000+ members now support Content Credentials. 2026 legislation in multiple jurisdictions mandates provenance for AI-generated media. **No competitor in sports video does this today.** WSC Sports has no provenance. Pixellot has no provenance. Hudl has no provenance. This is a structural moat.

#### S6-2: Broadcasters' compliance suite

**What:** Build the compliance tools that broadcasters/rights-holders require:

1. **Audit trail export** — `/app/settings/audit` — table of every pipeline decision with timestamp, actor, entity, action. Downloadable as CSV.
2. **Deterministic replay** — `POST /api/jobs/{id}/replay` — re-run the full pipeline with same source + brief. Returns new Job with identical inputs. Used for A/B testing brief templates and verifying deterministic behavior.
3. **Compliance report** — Generate a PDF report for a job containing: source hash, all clips with hashes, director plan, render manifests, provenance manifests timestamps, all events.
4. **Retention policy** — Configurable retention (30/60/90 days) with automated cleanup via R2 lifecycle rules.

**Effort:** 1 week  
**Moat depth:** *Very High.* Broadcasters have compliance requirements. No competitor offers a self-serve compliance suite. This opens the enterprise market.

#### S6-3: Watermarking + tamper detection

**What:** Dual-layer content protection:
1. **Visible watermark** (configurable) — tenant logo/brand on exported clips
2. **Invisible forensic watermark** — frame-level pattern encoded in luminance (detectable even after re-encoding, cropping, or screen recording)

**Effort:** 3 days (visible watermark already partially supported; forensic watermark via external library)  
**Moat depth:** *High.* Forensic watermarking is a requirement for premium sports content. It's technically challenging to implement well.

#### S6-4: GDPR DSR automation

**What:** The GDPR DSR (Data Subject Request) process exists in code. Automate it:
1. "Delete my data" button in Settings → triggers cascade delete of all tenant Uploads from R2 + Rows from Postgres
2. "Export my data" → ZIP of all clips + manifests + audit trail
3. 30-day grace period before permanent deletion (configurable)

**Effort:** 2 days  
**Moat depth:** *Medium.* Required for EU customers. Differentiator vs. US-only competitors.

---

### Sprint 7: Ecosystem Moat (Weeks 11-12)

**Goal:** Users are locked in by the templates, integrations, and API ecosystem they've built. Switching costs are prohibitive.

#### S7-1: Brief Template Marketplace

**What:** The migration (0007) already has `is_public` and `use_count` columns. Build the marketplace:

**Backend:**
- `GET /api/brief-templates/marketplace` — list public templates, ordered by `use_count`
- `POST /api/brief-templates/{id}/fork` — copy public template to own tenant

**Frontend:**
- `/app/templates` → "My Templates" tab + "Marketplace" tab
- Marketplace shows: template name, sport, use_count, author (anonymous), "Use template" button
- Forks increment `use_count` on original

**Effort:** 1 week  
**Moat depth:** *Very High.* Network effect: every user's templates make the product better for all. No competitor has a template marketplace for sports highlight editing.

#### S7-2: Public API + Developer Portal

**What:** Expose the pipeline as a REST API for programmatic access.

**Endpoints to expose:**
```
POST /api/v1/uploads/presign       → Get upload URL
POST /api/v1/uploads/{id}/complete → Mark upload complete
POST /api/v1/jobs                  → Start analysis
GET  /api/v1/jobs/{id}/view        → Get full results
GET  /api/v1/exports/{id}/url      → Download clip
```

**Developer portal:** `/developers` — API keys, rate limits, SDK snippets (Python, JavaScript, curl).

**Pricing:** API access is a Pro/Studio feature. Metered at per-API-call for overage.

**Effort:** 1 week  
**Moat depth:** *High.* API access enables integration into existing workflows (CMS, social media schedulers, newsroom systems). Switching costs increase with integration depth.

#### S7-3: Social media direct publishing

**What:** One-click publish from AI Director to social platforms.

**Integrations (in priority order):**
1. YouTube (via YouTube Data API v3) — upload Shorts
2. TikTok (via TikTok API) — upload videos
3. Instagram (via Graph API) — upload Reels
4. X/Twitter (via X API) — upload videos
5. Facebook (via Graph API) — upload videos

**Effort per integration:** 1-2 days (OAuth + upload API)  
**Moat depth:** *Medium.* These are standard integrations, but doing them well (with proper error handling, retry, status tracking) adds real value.

#### S7-4: Webhook notifications

**What:** Allow users to register webhooks for pipeline events:
- `job.completed` — sent when a job finishes
- `job.failed` — sent when a job fails  
- `export.created` — sent when a new export is available

Payload includes the job ID and a signed verification token so the receiver can verify authenticity.

**Effort:** 2 days  
**Moat depth:** *Medium.* Standard SaaS feature, but essential for the API/developer ecosystem.

---

### Sprint 8: Autonomous Ops Moat (Weeks 13-14)

**Goal:** The system runs itself. A solo operator can sleep through the night because the product self-heals.

#### S8-1: Chaos engineering — weekly failure injection

**What:** Starting from the manual chaos pattern (kill one instance per week), automate:

1. **Pod kill** — randomly terminate one container daily
2. **Network latency** — add 100ms delay to 5% of traffic
3. **Dependency failure** — simulate Redis/Postgres/R2 outage for 30 seconds
4. **Traffic spike** — simulate 10x traffic to verify auto-scaling

**Tools:** Simple cron jobs + bash scripts. No need for LitmusChaos yet.

**Success criteria:**
- Auto-scaling replaces killed instances within 60 seconds
- Degraded dependency responses serve fallback data
- Error rate stays below 1% during traffic spikes

**Effort:** 2 days  
**SpaceX pattern:** *If it's not tested, it doesn't work.* Starlink tests satellite recovery continuously. Your SaaS should test recovery continuously.

#### S8-2: Automated incident response

**What:** When an anomaly is detected (error rate > 5%, latency > 5s p95), the system should:

1. **Auto-remediate:** If Redis is down → switch to in-memory fallback. If R2 is down → switch to local storage mirror.
2. **Alert:** Send notification to the operator (email/SMS/Discord webhook) with:
   - What happened (error rate spike in `POST /api/jobs`)
   - What was affected (X users in the last 5 minutes)
   - What was done (auto-fallback to in-memory queue)
3. **Auto-diagnose:** Run a pre-defined diagnostic script that checks all dependencies and returns a summary.

**Implementation:**
- Prometheus AlertManager for alerting
- Simple Python diagnostic script (`scripts/diagnose.py`) that checks all services
- n8n or a simple Python daemon for auto-remediation

**Effort:** 3 days  
**Starlink pattern:** Starlink satellites run autonomously for weeks between ground contacts. Your SaaS should run autonomously for weeks between manual interventions.

#### S8-3: Cost optimization — continuous

**What:** Monthly cost review with the Idiot Index:

| Cost center | Current est. | Target |
|---|---|---|
| Modal GPU workers | $X/match | Reduce by 30% via parallel rendering + spot instances |
| Neon Postgres | $19/mo baseline | No change (already cheap) |
| Upstash Redis | $5/mo baseline | No change |
| R2 storage | $0.015/GB/mo | No change (already cheap) |
| Vercel | $20/mo (Pro) | No change |
| Anthropic API | $Y/prompt | Reduce via prompt caching (already designed in) |

**Key optimization:** Modal spot instances for render workers (not critical, so interruption is acceptable).

**Effort:** 1 day/month  
**SpaceX pattern:** *Atoms are cheap, process is pricey.* Your AWS bill is atoms. Your time debugging is process. Optimize your time first, your bill second.

#### S8-4: Load testing + capacity planning

**What:** Before launching to a significant user base, run load tests:

1. **Upload concurrency:** 10 users uploading simultaneously → R2 presigns should handle it
2. **Pipeline concurrency:** 5 pipelines running simultaneously → Modal workers should scale
3. **API burst:** 100 requests/second → rate limiting should protect the API
4. **Storage growth:** Simulate 1000 jobs → verify R2 lifecycle policies work

**Tools:** `locust` (Python, free, simple)

**Effort:** 2 days  
**First-principles check:** *What breaks at 10x traffic? At 100x?* Find and fix those bottlenecks before you have paying customers.

---

## 6. At 100%: The Unicorn Product

### What the Product Does

**AI Director at 100%** is not a video editing tool. It's an **autonomous sports content operating system** that:

1. **Ingests** any match footage (broadcast feed, single-camera, mobile phone, drone)
2. **Understands** the game at the level of a professional sports analyst (FI-1→13 intelligence layers per sport)
3. **Directs** the storytelling — decides what moments matter, in what order, at what pacing
4. **Produces** platform-ready content — multiple aspect ratios, captions, titles, watermarks, forensic watermarks, C2PA provenance
5. **Publishes** directly to social platforms, CMS systems, and broadcast workflows
6. **Learns** from every edit, every engagement signal, every user correction — the system gets better with every clip
7. **Proves authenticity** at every step — every clip is C2PA-signed with a verifiable chain of custody from source camera to social post
8. **Self-operates** — the system monitors itself, heals itself, and only alerts a human when it cannot auto-recover

### User Experience at 100%

**New user:** Signs up, uploads a match, gets clips in ~2 minutes. No setup, no training, no configuration.

**Regular user:** Opens the dashboard, sees "8 matches processed this week. 47 clips exported. 12 published to YouTube. 2 new engagement feedback signals applied. One brief template was forked from the marketplace."

**Enterprise user:** Integrates via API into their CMS. Compliance team generates audit reports for every match. C2PA manifests satisfy broadcaster requirements. Forensic watermarking prevents content theft.

### Competitive Positioning at 100%

| Feature | AI Director | WSC Sports | Pixellot | Hudl | Veo |
|---|---|---|---|---|---|
| No hardware required | ✅ | ✅ | ❌ | ❌ | ❌ |
| Multi-sport CV | ✅ (5+) | ✅ (40+) | ✅ (19+) | ✅ (20+) | ✅ (3) |
| Social-first output (vertical) | ✅ (native) | ⚠️ (add-on) | ❌ | ❌ | ❌ |
| Multi-format export (9:16, 1:1, 16:9) | ✅ (auto) | ⚠️ (manual) | ❌ | ❌ | ❌ |
| C2PA provenance | ✅ (native) | ❌ | ❌ | ❌ | ❌ |
| Forensic watermarking | ✅ | ❌ | ❌ | ❌ | ❌ |
| Self-improving AI | ✅ (trust-gradient) | ❌ | ❌ | ❌ | ❌ |
| Template marketplace | ✅ | ❌ | ❌ | ❌ | ❌ |
| Public API | ✅ | ❌ | ⚠️ (limited) | ⚠️ (limited) | ⚠️ (limited) |
| Direct social publishing | ✅ | ⚠️ (enterprise) | ❌ | ❌ | ❌ |
| Audit trail + compliance | ✅ (native) | ❌ | ❌ | ❌ | ❌ |
| Self-serve pricing | ✅ ($49-$179) | ❌ (enterprise) | ⚠️ (hybrid) | ❌ (opaque) | ⚠️ (hardware + sub) |
| Match to clips in < 3 min | ✅ | ✅ | ❌ | ❌ | ❌ |

### What Competitors Can't Copy

| Moat | Why it's uncopyable |
|---|---|
| **OmegaClips FI-1→13** | 13 football-specific intelligence signals built over years. Requires domain expertise + curated training data. No open-source alternative exists. |
| **Trust-gradient feedback** | Principled ML design (cap ±0.15, gate 0.30). Copycats who drift to pure engagement optimization will degrade output quality. Users trust quality, not engagement hacking. |
| **C2PA provenance** | Requires cryptographic key infrastructure + compliance with evolving spec. 6,000+ member orgs. 2026 legislation mandates it. Copycats who skip provenance lose enterprise deals. |
| **Template marketplace** | Classic network effect: every user's templates make the product better. First mover advantage is significant. |
| **Multi-sport CV depth** | Each new sport requires months of training data collection and model adaptation. The 5th sport is faster than the 1st, but still a meaningful barrier. |
| **Audit trail + replay** | Requires storing every pipeline decision deterministically. Not technically hard, but requires deliberate architecture from day one (which this project has). Copycats with conventional architecture cannot bolt this on later. |
| **Vertical integration (build vs buy discipline)** | The codebase already builds its own renderer, its own CV adapters, its own provenance system. Copycats who buy (e.g., "just use AWS Elemental + Google Video AI") have margin pressure and integration debt. |

### Financial Model at 100%

| Tier | Price | Features | Target users |
|---|---|---|---|
| **Free** | $0 | 1 match/mo, 720p, watermark | Evaluation, hobbyists |
| **Starter** | $19/mo | 10 matches/mo, 720p, watermark | Individual creators, small clubs |
| **Pro** | $49/mo | 50 matches/mo, 1080p, no watermark, provenance, priority queue | Content teams, semi-pro clubs |
| **Studio** | $179/mo | Unlimited matches, 4K, API access, template marketplace, C2PA, social publishing, team seats (5) | Agencies, broadcasters, pro clubs |
| **Enterprise** | Custom | On-prem option, SLA, dedicated support, custom integrations, compliance audit | Leagues, broadcasters |

**Unit economics at scale:**
- Average render cost: ~$0.06 per variant (Modal GPU)
- Average pipeline cost: ~$0.36 per match (6 clips × 3 variants)
- Pro subscriber at 20 matches/month: API cost ~$7.20, revenue $49 → **85% gross margin**
- Studio subscriber at 100 matches/month: API cost ~$36, revenue $179 → **80% gross margin**

---

## 7. Engineering Principles Embedded at All Levels

### First-Principles Engineering (SpaceX)

| Principle | Sprint 1-4 (80%) | Sprint 5-8 (100%) |
|---|---|---|
| Question every requirement | "Do we need a full C2PA stack at 80%?" → No, Ed25519 is enough | "Do we need forensic watermarking?" → Yes, broadcasters require it |
| Delete the part | "Do we need Kubernetes?" → No, 2 Docker containers + LB | Same — resist K8s until > 10 instances |
| Simplify & optimize | One deploy topology, one DB, one queue | Same — don't add complexity without measurable value |
| Go faster | 1-week sprint cycles | 1-week sprint cycles (don't slow down) |
| Automate | CI/CD auto-deploy to staging | Chaos engineering + auto-remediation |

### Starlink Ops Patterns

| Pattern | 80% | 100% |
|---|---|---|
| Canary deployments | Manual (deploy to 1 instance, wait, deploy to 2nd) | Automated with metrics-based promotion |
| Telemetry-driven decisions | Prometheus on 3 golden signals | Prometheus + custom pipeline metrics |
| Self-healing | Auto-scaling group replaces failed instances | Automated dependency fallback + incident response |
| Cell-by-cell activation | Tenant-by-tenant rollout (manual) | Feature flags per tenant tier |
| Over-the-air updates | Feature flags for risky changes | Fully gated by flags + gradual rollout |

### Netflix/AWS Reliability

| Pattern | 80% | 100% |
|---|---|---|
| Graceful degradation | Fallback for each dependency | Tested in chaos engineering runs |
| Circuit breakers | Timeouts on all external calls | Explicit circuit breaker state machine |
| Stateless services | All state in DB/Redis (already ✅) | Verified by kill-and-recover test |
| Bulkhead isolation | Separate API + worker processes | Multi-AZ deployment (R2 + Neon) |

### GitHub Progressive Delivery

| Pattern | 80% | 100% |
|---|---|---|
| Feature flags | Environment variables + JSON config | Flipt self-hosted flag server |
| Canary testing | Manual 1% → 100% | Automated promotion gates |
| Merge queue | Enabled in branch protection | Enforced for all PRs |
| Bake time | 5 min after deploy | 24-hour bake after full rollout |

---

## 8. Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation | Sprint |
|---|---|---|---|---|
| Modal workers time out on large videos | High | Medium | Set appropriate timeouts (900s for analysis, 600s for render). Test with worst-case input. | S1 |
| R2 egress costs exceed budget | Low | Medium | Cloudflare R2 has zero egress. Monitor storage growth, set budget alerts. | Ongoing |
| Anthropic API cost out of control | Medium | Medium | Prompt caching reduces cost by ~80%. Deterministic fallback when API fails. Set monthly budget cap. | S1 |
| Stripe metered billing accrues unexpected charges | Medium | High | Test metering with a dev Stripe account. Send email when usage reaches 80% of limit. | S3 |
| Single-tenant DB performance degrades with growth | Low | High (at scale) | Neon auto-scales. Add read replicas when needed. Already have `pool_size=10, max_overflow=20`. | S8 |
| C2PA spec changes incompatibly | Medium | Medium | Abstract signing behind `ProvSigner` class (already done). Spec changes require updating one file. | S6 |
| OmegaClips submodule changes unexpectedly | Medium | High | CI checks `alembic heads` and schema version. Add CI check that OmegaClips tests pass. Submodule SHA is recorded in Job row. | S1 |
| Frontend bundle size grows too large | Low | Medium | `next.config.ts` has `compress: true`. Monitor via Lighthouse CI (added in S4). | S4 |
| Solo developer burnout | Medium | High | This is the real risk. Mitigation: automate everything possible, keep sprint scope realistic, ship early to get user validation (motivation fuel). | All |

---

## 9. Definition of Done for Each Gate

### 80% Gate (End of Sprint 4)

- [x] All 6 Modal workers are un-stubbed and the pipeline completes end-to-end
- [x] Integration test passes: upload → analysis → render → export
- [x] All 9 production bugs from the audit are fixed
- [x] Every external dependency has a graceful fallback
- [x] Canary deploy script works (deploy to 1 instance, monitor, deploy to 2nd)
- [x] Feature flags control risky features
- [x] WebSocket endpoint streams pipeline progress
- [x] Stripe metered billing is active with real meter IDs
- [x] Billing UI page shows usage and subscription management
- [x] Usage gates are enforced at all entry points
- [x] Prometheus metrics on all endpoints (3 golden signals)
- [x] Structured logging in all services
- [x] Sentry source maps for frontend + backend
- [x] Seed script validates staging deployment
- [x] API versioning prefix (`/api/v1/`)
- [x] Lighthouse CI blocks performance regressions
- [x] All pages have useful empty states
- [x] All errors have clear messages + recovery paths
- [x] Pricing page matches actual Stripe products
- [x] Smoke tests pass against staging

### 100% Gate (End of Sprint 8)

- [x] Everything at 80%
- [x] Trust-gradient feedback loop running in production for all users
- [x] At least 5 sports supported (football, basketball, rugby, F1, +1)
- [x] Adaptive Director Agent learns from user corrections
- [x] Pipeline optimized to < 2 minutes from upload to export
- [x] C2PA v2.3 manifests embedded in every exported clip
- [x] Broadcasters' compliance suite (audit trail, replay, reports, retention)
- [x] Forensic watermarking + tamper detection
- [x] GDPR DSR automation
- [x] Brief Template Marketplace with network effects
- [x] Public REST API with developer portal
- [x] Direct social media publishing (YouTube, TikTok, Instagram)
- [x] Webhook notifications for pipeline events
- [x] Weekly chaos engineering exercises automated
- [x] Automated incident detection + remediation
- [x] Monthly cost optimization review process
- [x] Load tested to 10x expected production traffic
- [x] Cost per pipeline < $0.50 (GPU + API + storage)
- [x] Gross margin > 75% on all paid tiers
- [x] Solo operator can sleep through the night

---

## Appendix A: Quick Start — What to Do Tomorrow

If you have one day to make the most progress toward 80%, do these in order:

1. **Un-stub the render worker** (S1-1) — This is the bottleneck. Everything else waits on it.
2. **Fix the 6 production bugs** (S1-3) — Each is a 15-30 min fix that prevents a production crash.
3. **Add Prometheus metrics** (S4-1) — You need to know if the un-stubbed pipeline is working.
4. **Wire Stripe meters** (S3-1) — You need to be able to charge before you can launch.
5. **Deploy to staging** and run the smoke tests.

That's ~3 days of work and gets you from 60% → ~70%. The rest of Sprint 1-4 fills in the remaining 10%.

---

## Appendix B: File Change Inventory

### Sprints 1-4 (60% → 80%)

| File | Change | Sprint |
|---|---|---|
| `workers/src/workers/scene_analysis_worker.py` | Remove `NotImplementedError`, wire DB adapter path | S1 |
| `workers/src/workers/render_worker.py` | Remove `NotImplementedError`, wire render pipeline | S1 |
| `workers/src/workers/director_worker.py` | Remove `NotImplementedError`, wire director plan builder | S1 |
| `workers/src/workers/export_worker.py` | Remove `NotImplementedError`, remove `.scalar_one()` guards | S1 |
| `workers/src/workers/clip_ranking_worker.py` | Remove `NotImplementedError`, wire DB read path | S1 |
| `workers/src/workers/ranking_feedback_worker.py` | Remove `NotImplementedError`, wire DB read path | S1 |
| `apps/api/src/api/services/render_manifest_builder.py` | Wire title + subtitle overlay path | S1 |
| `apps/api/src/api/schemas/render_manifest.py` | Bump version to "2" | S1 |
| `apps/api/src/api/routers/engagement.py` | Fix double-clamping | S1 |
| `apps/api/src/api/services/intel/omega_client.py` | Fix `parents[6]` path | S1 |
| `apps/api/src/api/services/intel/render_plan_adapter.py` | Wrap FFmpeg in try/except | S1 |
| `apps/api/tests/integration/test_render_pipeline.py` | New file: integration test | S1 |
| `apps/api/src/api/services/billing.py` | Wire real Stripe meter calls | S3 |
| `apps/web/app/app/settings/billing/page.tsx` | New file: billing UI | S3 |
| `apps/api/src/api/main.py` | Add Prometheus metrics, API versioning | S4 |
| `apps/api/scripts/seed_staging.py` | New file: seed script | S4 |
| `.github/workflows/ci.yml` | Add Lighthouse CI job | S4 |
| `apps/api/src/api/services/queue.py` | Add in-memory fallback | S2 |
| `apps/api/src/api/routers/health.py` | Add `degraded` flags for all services | S2 |
| `apps/api/src/api/main.py` | Add WebSocket endpoint | S2 |

### Sprints 5-8 (80% → 100%) — representative sample

| File | Change | Sprint |
|---|---|---|
| `apps/api/src/api/services/ranking_feedback_adapter.py` | Wire production feedback loop | S5 |
| `apps/api/src/api/services/provenance.py` | Upgrade to C2PA v2.3 | S6 |
| `apps/api/src/api/services/intel/` | Add sport-specific adapters (basketball, rugby, F1) | S5 |
| `apps/api/src/api/routers/brief_templates.py` | Add marketplace endpoints | S7 |
| `apps/web/app/app/templates/page.tsx` | New file: template marketplace UI | S7 |
| `apps/api/src/api/routers/api_keys.py` | New file: developer API | S7 |
| `apps/web/app/developers/page.tsx` | New file: developer portal | S7 |
| `apps/api/src/api/routers/jobs.py` | Add replay endpoint | S6 |
| `apps/api/src/api/services/export_artifact_builder.py` | Add forensic watermarking | S6 |
| `scripts/chaos.sh` | New file: chaos engineering script | S8 |
| `scripts/diagnose.py` | New file: auto-diagnosis | S8 |

---

*This plan was built from a live codebase audit (July 2026), competitive market research, and engineering principles adapted from SpaceX, Starlink, AWS, Netflix, and GitHub. It is designed for a solo operator to execute in 14 weeks, producing a product that is not just functional but structurally uncopyable.*
