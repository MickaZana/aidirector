# Beta Launch Runbook

## Overview

This runbook contains the step-by-step procedure for launching the AI Director beta. Follow each section sequentially. Do not skip steps.

**Version:** 1.0  
**Last updated:** 2026-07-30  
**Owner:** Platform engineering  
**Estimated duration:** 2-3 hours  

---

## Pre-Flight Checklist (T-24h)

### 1. Environment Validation

```bash
# Verify all required environment variables are set on production
# Frontend (Vercel Dashboard):
# - NEXT_PUBLIC_API_URL         → https://api.aidirector.app
# - NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY → pk_xxx
# - NEXT_PUBLIC_SENTRY_DSN      → https://xxx@xxx.ingest.sentry.io/xxx

# Backend (docker-compose / hosting):
# - DATABASE_URL                → postgresql://...
# - REDIS_URL                   → rediss://...
# - R2_ACCOUNT_ID / KEY / SECRET
# - CLERK_SECRET_KEY / WEBHOOK_SECRET
# - STRIPE_SECRET_KEY / WEBHOOK_SECRET
# - ANTHROPIC_API_KEY
# - MODAL_TOKEN_ID / SECRET
# - SENTRY_DSN
```

**Verify:**
- [ ] All env vars are set (non-empty) in production
- [ ] Clerk publishable key starts with `pk_`
- [ ] API URL starts with `https://`
- [ ] Sentry DSN starts with `https://`
- [ ] Stripe keys are production (not `sk_test_`) — **critical**

### 2. Build Verification

```bash
# From repo root
pnpm install --frozen-lockfile

# TypeScript
pnpm --filter @aidirector/web typecheck
# Expected: no errors

# Unit tests
pnpm --filter @aidirector/web test
# Expected: all 125+ tests pass

# Production build
pnpm --filter @aidirector/web build
# Expected: build succeeds, no warnings

# Backend tests (if available)
cd apps/api && uv run pytest tests/ -v --tb=short
# Expected: all tests pass
```

- [ ] `pnpm typecheck` passes (0 errors)
- [ ] `pnpm test` passes (all tests)
- [ ] `pnpm build` succeeds
- [ ] Lighthouse CI score ≥ 85 performance, ≥ 90 accessibility

### 3. Infrastructure Health

```bash
# Check all dependencies are reachable from production
curl -f https://api.aidirector.app/health
curl -f https://api.aidirector.app/health/db
curl -f https://api.aidirector.app/health/queue
```

- [ ] API health endpoint returns 200
- [ ] Database health returns 200 (SELECT 1)
- [ ] Redis/queue health returns 200
- [ ] R2 bucket accessible (presign test)
- [ ] Clerk webhooks reachable
- [ ] Stripe webhooks reachable

### 4. Database

```bash
# Run pending migrations
cd apps/api && uv run alembic upgrade head
```

- [ ] All migrations applied (single head, no divergence)
- [ ] Schema version checks pass
- [ ] Seed data exists for demo tenant (if applicable)

### 5. Monitoring & Alerting

- [ ] Sentry error tracking enabled for frontend + backend
- [ ] Source maps uploaded (Sentry)
- [ ] Logfire (or equivalent) structured logging active
- [ ] Health check endpoints registered with monitoring
- [ ] Alert threshold: error rate > 5% triggers notification
- [ ] Alert threshold: p95 latency > 5s triggers notification

---

## Launch Procedure (T-0)

### Step 1: Deploy Backend (API + Workers)

```bash
# 1. Deploy API containers
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api

# 2. Verify health
curl -f https://api.aidirector.app/health
sleep 5
curl -f https://api.aidirector.app/health/db

# 3. Deploy workers
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d worker

# 4. Verify worker connectivity
# Check worker logs for "subscribed to q:render-cpu, q:cv, q:llm, q:export"

# 5. Deploy Modal workers (if applicable)
cd apps/api && uv run modal deploy modal_app.py
```

**Rollback:** `docker compose -f docker-compose.prod.yml down api && docker compose up -d api` (previous image)

- [ ] API deployed and healthy
- [ ] Workers deployed and connected to queues
- [ ] Modal workers deployed (if used)

### Step 2: Deploy Frontend

```bash
# Vercel auto-deploys from main branch
# Or manually:
pnpm dlx vercel deploy --prod --token="$VERCEL_TOKEN" --confirm
```

**Verify:**
- [ ] Landing page loads (https://aidirector.app)
- [ ] Sign-in flow works (Clerk)
- [ ] Upload page loads (https://aidirector.app/app/upload)
- [ ] Terms & privacy pages load
- [ ] Error boundary renders correctly (test by navigating to /nonexistent)
- [ ] CSP headers present (check browser dev tools → Network → Response Headers)

**Rollback:** Vercel dashboard → Previous deployment → Promote

### Step 3: DNS & SSL

- [ ] Custom domain resolves (aidirector.app)
- [ ] SSL certificate valid (no browser warnings)
- [ ] API subdomain resolves (api.aidirector.app)
- [ ] CORS configured for production origins

### Step 4: Final Smoke Tests

```bash
# Run the smoke test script
node scripts/smoke-test.js
```

**Manual smoke tests:**
- [ ] Anonymous user → landing page → "Get started" → Clerk sign-up
- [ ] Upload a small video file → verify upload completes
- [ ] Verify analytics `project_started` event fires
- [ ] Verify processing starts (via UI polling)
- [ ] Navigate to clips page → empty state displays correctly
- [ ] Navigate to settings → billing page loads
- [ ] Rate limiter: rapidly click submit → 429 toast appears
- [ ] Offline: disconnect network → offline banner appears → reconnect → banner disappears
- [ ] Feedback widget appears after project completion (if applicable)
- [ ] Onboarding overlay shows on first visit

---

## Post-Launch Monitoring (T+0 to T+24h)

### First Hour (T+0 to T+1)
- [ ] Monitor Sentry error rate (should be 0 new errors)
- [ ] Verify analytics events arriving (check localStorage/flush)
- [ ] Watch API response times (p95 < 2s)
- [ ] Check worker queue depths (should process and drain)
- [ ] Verify all 3 health endpoints remain green

### First Day (T+1 to T+24)
- [ ] Review error logs for any patterns
- [ ] Check user sign-up rate
- [ ] Monitor R2 storage growth
- [ ] Verify Stripe webhook delivery (if billing active)
- [ ] Review Lighthouse CI report from latest main build
- [ ] Check feedback widget submissions (if any)
- [ ] Performance check: run Lighthouse against production

---

## Rollback Procedure

### Immediate Rollback (any step fails)
```
1. Frontend: Vercel dashboard → promote previous deployment
2. API: docker-compose -f docker-compose.prod.yml down api
   docker-compose up -d api  # (uses previous tag)
3. Workers: docker-compose -f docker-prod-compose.yml down worker
4. DNS: Point back to previous IP if changed
5. Announce: Post in #status channel
```

### Rollback Criteria
Trigger rollback if any of:
- Error rate > 5% for > 5 minutes
- p95 API latency > 5s for > 5 minutes
- User-facing 500 errors on core flows (upload, auth)
- Data integrity issue detected
- Security vulnerability discovered

---

## Communication Plan

| Timing | Channel | Message |
|--------|---------|---------|
| T-24h | Internal | "Beta launch scheduled for [date] [time]" |
| T-1h | Internal | "Launch pre-flight started" |
| T+0 | Internal | "Launch initiated" |
| T+5min | Internal | "Frontend deployed, verifying" |
| T+15min | Internal | "All systems healthy" |
| T+1h | Internal | "1-hour check: [status]" |
| T+24h | Internal | "24-hour post-launch review [link]" |

---

## Beta User Support

### Known Beta Limitations
- Pipeline workers: scene_analysis and director workers use fixture/logic paths (not full Modal GPU)
- Rendering: basic FFmpeg only; sports_hype and documentary render styles are stubs
- Performance feedback: requires manual engagement data entry
- Maximum upload size: 3 GB (configurable in production config)
- Supported formats: MP4, MOV, AVI, MKV, WebM

### Support Contact
- **Email:** mike.mediainstitute@gmail.com
- **Response time:** < 4 hours during business hours (UTC+1)
- **Severity classification:**
  - P0: Pipeline completely down → immediate response
  - P1: Major feature broken → 2-hour response
  - P2: Minor feature broken → next business day
  - P3: Cosmetic/UX → next sprint

---

## Appendices

### A. Quick Reference: Key URLs
| Resource | URL |
|----------|-----|
| Production site | https://aidirector.app |
| API base | https://api.aidirector.app |
| Sentry dashboard | https://sentry.io/organizations/... |
| Vercel dashboard | https://vercel.com/... |
| Clerk dashboard | https://clerk.com/... |
| Stripe dashboard | https://dashboard.stripe.com/... |
| Neon (DB) | https://console.neon.tech/... |
| Upstash (Redis) | https://console.upstash.com/... |
| Cloudflare R2 | https://cloudflare.com/... |

### B. Quick Reference: Commands
| Action | Command |
|--------|---------|
| Deploy frontend | `pnpm dlx vercel deploy --prod --token="$TOKEN" --confirm` |
| Deploy API | `docker compose -f docker-compose.prod.yml up -d api` |
| Run migrations | `cd apps/api && uv run alembic upgrade head` |
| Check health | `curl https://api.aidirector.app/health` |
| View API logs | `docker compose logs -f api` |
| View worker logs | `docker compose logs -f worker` |
| Run tests | `pnpm test` (frontend), `uv run pytest` (backend) |
| Type-check | `pnpm typecheck` |

### C. Incident Response Template

```
## Incident Report

**Date:** YYYY-MM-DD
**Severity:** P0/P1/P2
**Detected at:** HH:MM UTC
**Resolved at:** HH:MM UTC
**Duration:** XX minutes

### What happened
[Description of the incident]

### Impact
[What users experienced, how many affected]

### Root cause
[What went wrong]

### Resolution
[What was done to fix it]

### Preventative measures
[What will prevent recurrence]

### Action items
- [ ] Item 1
- [ ] Item 2
```
