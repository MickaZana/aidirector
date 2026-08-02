# Railway deployment checklist

This document describes the service configuration without containing credentials.
Create one Railway project with Railway PostgreSQL and Railway Redis, then add
three services from this repository: Web, API, and Worker.

## Services

| Service | Source/configuration | Build | Start | Readiness |
|---|---|---|---|---|
| Web | `apps/web/railway.toml` | `pnpm --filter @aidirector/web build` | `pnpm --filter @aidirector/web start` | `GET /` |
| API | `apps/api/railway.api.toml` | `apps/api/Dockerfile` | Docker default, using Railway `$PORT` | `GET /health`, `/health/db`, `/health/queue`, `/health/r2` |
| Worker | `apps/api/railway.worker.toml` | `apps/api/Dockerfile` | `rq worker --url $REDIS_URL q:render-cpu q:cv q:llm q:export` | worker logs + Redis connectivity |

Run the API migration once, before serving traffic:

```text
alembic upgrade head
```

The API and Worker must share the same Railway `DATABASE_URL` and `REDIS_URL`.
The worker uses Linux RQ; the Windows `SimpleWorker` workaround is not used.

## Variables

Set these in Railway service variables. Never commit their values.

### PUBLIC

| Variable | Required | Used by |
|---|---|---|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Web/Clerk browser SDK |
| `NEXT_PUBLIC_API_URL` | Yes | Web API client; deployed API URL |
| `NEXT_PUBLIC_SENTRY_DSN` | Optional | Web error reporting |

### DATABASE and REDIS

| Variable | Required | Used by |
|---|---|---|
| `DATABASE_URL` | Yes | API, Worker, Alembic |
| `REDIS_URL` | Yes | API queue producer, Worker consumer |

### CLERK

| Variable | Required | Used by |
|---|---|---|
| `CLERK_PUBLISHABLE_KEY` | Yes | API configuration |
| `CLERK_SECRET_KEY` | Yes | API token verification |
| `CLERK_JWKS_URL` | Yes | API JWT verification |
| `CLERK_WEBHOOK_SECRET` | Optional | Clerk webhook validation |

### R2

| Variable | Required | Used by |
|---|---|---|
| `R2_ACCOUNT_ID` | Yes | API R2 endpoint |
| `R2_ACCESS_KEY_ID` | Yes | API presigning/storage |
| `R2_SECRET_ACCESS_KEY` | Yes | API presigning/storage |
| `R2_BUCKET` | Yes | API presigning/storage |
| `R2_PUBLIC_BASE_URL` | Optional | Public media URLs |

### AI and processing

| Variable | Required | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | Required for enabled LLM enrichment | Worker/AI adapter |
| `DEEPGRAM_API_KEY` | Optional, required for transcription | Worker |
| `MODAL_TOKEN_ID` | Required if Modal workers are enabled | Modal deployment |
| `MODAL_TOKEN_SECRET` | Required if Modal workers are enabled | Modal deployment |
| `FFMPEG_DRAWTEXT_FONT` | Optional | API/Worker rendering; Docker supplies a default |

### STRIPE

`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_METER_ASR_MINUTES`, `STRIPE_METER_GPU_SECONDS`,
`STRIPE_METER_EXPORT_COUNT`, `STRIPE_PRICE_PRO`, and `STRIPE_PRICE_STUDIO`.
Required according to the enabled billing/metering paths; optional for a
non-billing staging deployment.

### APPLICATION and OBSERVABILITY

| Variable | Required | Used by |
|---|---|---|
| `ENV=production` | Yes | API production behavior |
| `ALLOWED_ORIGINS` | Yes | API CORS; include the Railway Web origin |
| `PROVENANCE_SIGNING_KEY_B64` | Required for signed artifacts | API/Worker provenance |
| `PROVENANCE_KEY_ID` | Optional | Provenance key label |
| `SENTRY_DSN` | Optional | API error reporting |
| `LOGFIRE_TOKEN` | Optional | API structured logging |

## Clerk and R2 operator actions

After Railway assigns the Web and API domains:

1. Confirm the Clerk publishable and secret keys are from the same instance.
2. Add the Railway Web origin to Clerk allowed origins.
3. Add the Railway Web origin to Clerk redirect/origin settings as required by the selected sign-in flow.
4. Register Clerk webhooks against the deployed API webhook route.
5. Add the Railway Web origin to the R2 bucket CORS policy for `PUT` and `Content-Type`.
6. Set `NEXT_PUBLIC_API_URL` to the deployed API URL and `ALLOWED_ORIGINS` to the deployed Web origin.

## E2E

The existing `e2e/football-real.spec.ts` remains unchanged. Select the target with:

```text
E2E_BASE_URL=https://<railway-web-domain>
E2E_AUTH_STATE=<legitimate external storage-state path>
E2E_FOOTBALL_MEDIA=<authorized local media path>
```

Do not store authentication state or media in the repository.
