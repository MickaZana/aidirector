# AI Director — Production Deploy Runbook

**Audience:** solo operator (Mike) or on-call  
**Stack:** Neon Postgres · Upstash Redis · Modal (GPU/CPU workers) · Vercel (Next.js) · Cloudflare R2 · Clerk · Stripe

---

## 0. Pre-flight checklist

Before any deploy, confirm:

- [ ] `git status` is clean on `main`
- [ ] CI is green: `api-test`, `api-alembic-check`, `web-build`
- [ ] `alembic heads` shows exactly **one** head (`uv run alembic heads` from `apps/api/`)
- [ ] `.env.production` (or Vercel/Modal secrets) contains all critical vars (see §7)

---

## 1. Database migration

Run from `apps/api/`:

```bash
# Verify current state
uv run alembic current

# Apply pending migrations
uv run alembic upgrade head

# Confirm
uv run alembic current
```

If the migration fails mid-way, roll back the last revision:

```bash
uv run alembic downgrade -1
```

Never run migrations concurrently. Neon supports branching — create a branch to test against production data before applying to main.

---

## 2. API server (Docker / Fly.io / Railway)

### Docker build

```bash
cd apps/api
docker build -t aidirector-api:$(git rev-parse --short HEAD) .
```

### Run locally against production DB (dry-run)

```bash
docker run --rm \
  --env-file .env.production \
  -p 8000:8000 \
  aidirector-api:<tag>
```

Check `GET /health` → `{"status":"ok"}` and `GET /health/queue` → queue depths.

### Deploy to Railway / Fly

The Dockerfile is the deploy unit. Platform-specific steps:

**Railway:**
```bash
railway up --service aidirector-api
```

**Fly.io:**
```bash
fly deploy --app aidirector-api
```

Wait for health checks to pass before proceeding.

---

## 3. RQ worker

The worker uses the same Docker image with a different `CMD`. On Railway/Fly, add a second service pointing at the same image:

```bash
rq worker --url $REDIS_URL q:render-cpu q:cv q:llm q:export
```

Or with docker-compose in production mode:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d worker
```

Verify the worker is polling:

```bash
redis-cli -u $REDIS_URL KEYS "rq:queue:*"
# Expect keys like rq:queue:q:render-cpu
```

---

## 4. Modal workers

Modal handles GPU render and CV analysis jobs. Deploy after every change to `modal_app.py` or `workers/`:

```bash
cd apps/api
modal deploy modal_app.py
```

This registers:
- `run_render` — stateless render function
- `run_scene_analysis` — placeholder (Sprint 3 stub)
- `drain_render_queue` — cron (every minute) that pops from RQ and spawns `run_render`

Confirm deployment:

```bash
modal app list
# Expect: aidirector-modal  DEPLOYED
```

Tail logs for the first few minutes:

```bash
modal logs aidirector-modal --tail
```

---

## 5. Next.js frontend (Vercel)

```bash
cd apps/web
pnpm build          # verify locally
# Then push to main — Vercel auto-deploys on merge
```

Or trigger manually:

```bash
vercel --prod
```

**Required Vercel env vars** (set in Vercel dashboard, not committed):

| Var | Notes |
|-----|-------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk dashboard → API Keys |
| `CLERK_SECRET_KEY` | same |
| `NEXT_PUBLIC_API_URL` | e.g. `https://api.aidirector.io` |

---

## 6. Webhook registration

### Stripe

1. Go to Stripe dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://api.aidirector.io/api/webhooks/stripe`
3. Events to listen for:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy the signing secret → set `STRIPE_WEBHOOK_SECRET` in production env

### Clerk

1. Clerk dashboard → Webhooks → Add endpoint
2. URL: `https://api.aidirector.io/api/webhooks/clerk`
3. Events: `user.created`, `user.updated`, `user.deleted`, `organization.created`, `organizationMembership.created`
4. Copy the signing secret → set `CLERK_WEBHOOK_SECRET` in production env

---

## 7. Required environment variables

### Critical (app refuses to start without these)

| Var | Where to get it |
|-----|----------------|
| `DATABASE_URL` | Neon dashboard → Connection string (pooled) |
| `REDIS_URL` | Upstash dashboard → REST URL |
| `CLERK_SECRET_KEY` | Clerk dashboard → API Keys |
| `CLERK_PUBLISHABLE_KEY` | same |
| `CLERK_WEBHOOK_SECRET` | Clerk dashboard → Webhooks → signing secret |

### Warn-only (app degrades gracefully but ops should be alerted)

| Var | Purpose |
|-----|---------|
| `R2_ACCOUNT_ID` | Cloudflare R2 uploads |
| `R2_ACCESS_KEY_ID` | same |
| `R2_SECRET_ACCESS_KEY` | same |
| `R2_BUCKET` | same |
| `STRIPE_SECRET_KEY` | Billing |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook validation |
| `ANTHROPIC_API_KEY` | AI plan generation |
| `PROVENANCE_SIGNING_KEY_B64` | Ed25519 clip signing |
| `SENTRY_DSN` | Error tracking |
| `LOGFIRE_TOKEN` | Structured logging |

### Optional tuning

| Var | Default | Notes |
|-----|---------|-------|
| `FFMPEG_DRAWTEXT_FONT` | set in Dockerfile | Font path for title burn-in |
| `ALLOWED_ORIGINS` | `["http://localhost:3000"]` | CORS; set to production domain |
| `ENV` | `development` | `production` disables debug pages |
| `PROVENANCE_KEY_ID` | `default-v1` | Key rotation label |

---

## 8. Smoke test after every deploy

```bash
# Set STAGING_API_URL (or PRODUCTION_API_URL) and run:
STAGING_API_URL=https://api.aidirector.io uv run pytest tests/smoke/ -v
```

Expected output: both `/health` and `/health/queue` return 200.

---

## 9. Rollback procedure

| Layer | Rollback |
|-------|----------|
| DB migration | `uv run alembic downgrade -1` (test on Neon branch first) |
| API image | Re-deploy previous Docker tag |
| Modal | `modal deploy` the previous commit's `modal_app.py` |
| Next.js | Vercel dashboard → Deployments → Promote previous |
| Stripe/Clerk webhooks | No rollback needed — idempotent |

---

## 10. Key URLs

| Resource | URL |
|----------|-----|
| API health | `https://api.aidirector.io/health` |
| API queue health | `https://api.aidirector.io/health/queue` |
| API docs (staging only) | `https://api.aidirector.io/docs` |
| Neon console | https://console.neon.tech |
| Upstash console | https://console.upstash.com |
| Modal dashboard | https://modal.com/apps |
| Vercel dashboard | https://vercel.com/dashboard |
| Clerk dashboard | https://dashboard.clerk.com |
| Stripe dashboard | https://dashboard.stripe.com |
| Cloudflare R2 | https://dash.cloudflare.com |
