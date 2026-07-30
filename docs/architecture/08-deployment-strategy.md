# Deployment Strategy

## CI/CD Pipelines

### CI (`.github/workflows/ci.yml`) — Runs on every push/PR

| Job | What it does |
|---|---|
| `api-test` | UV install → pytest unit tests → schema version guard |
| `api-alembic-check` | Verify single Alembic head (no orphan migrations) |
| `web-test` | pnpm install → vitest |
| `web-build` | pnpm install → `tsc --noEmit` → `next build` |
| `lighthouse` | Lighthouse CI for performance regression (continue-on-error) |

### Deploy (`.github/workflows/deploy.yml`) — Runs on push to `main`

| Job | What it does |
|---|---|
| `web-deploy` | Vercel deploy (`vercel deploy --prod`) |
| `api-deploy` | Modal deploy (`uv run modal deploy modal_app.py`) |
| `infra-deploy` | Pulumi preview + up (R2 bucket, Vercel project, GitHub secrets) |

## Deployment Sequence

```bash
# 1. Pulumi — create cloud resources (one-time setup)
cd infra
pulumi config set cloudflare:apiToken --secret
pulumi config set vercel:token --secret
pulumi config set github:token --secret
pulumi up

# 2. Modal — deploy backend workers
cd apps/api
modal secret create aidirector-db DATABASE_URL=...
modal secret create aidirector-redis REDIS_URL=...
modal secret create aidirector-r2 R2_ACCOUNT_ID=...  ...
modal secret create aidirector-signing PROVENANCE_SIGNING_KEY_B64=...
modal secret create aidirector-anthropic ANTHROPIC_API_KEY=...
modal deploy apps/api/modal_app.py

# 3. Push to main → GitHub Actions deploys frontend to Vercel
git push origin main

# 4. Configure webhooks
#    Clerk → POST {API_URL}/webhooks/clerk
#    Stripe → POST {API_URL}/webhooks/stripe
```

## Canary Deployments

For a solo operator, the canary strategy is:

```bash
# Deploy to instance 1 → wait 5 min → monitor → deploy to instance 2
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale api=1
# Wait, check health, error rate, latency
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale api=2
```

## Rollback

```bash
# Revert to previous Docker image tag
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d \
  --scale api=2 --no-build
```

## Environment Validation

At startup, the frontend validates required environment variables via `config/validateEnvironment.ts`:

- `NEXT_PUBLIC_API_URL` — must be a valid HTTP(S) URL
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` — must start with `pk_`
- `NEXT_PUBLIC_SENTRY_DSN` — must be a valid Sentry DSN (optional)
