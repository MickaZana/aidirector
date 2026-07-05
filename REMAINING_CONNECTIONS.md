# Remaining Connections — API Keys & Webhooks

> These are the manual setup steps still needed to go from code → fully live production.
> Each section marks what needs to be created, what env vars it feeds, and where to configure it.

---

## 1. 🗄️ Neon Postgres (Database)

| Item | Detail |
|------|--------|
| **Provider** | [neon.tech](https://neon.tech) |
| **What to do** | Create a project, get the connection string |
| **Env var** | `DATABASE_URL` |
| **Where used** | `apps/api/` — all DB operations |
| **Pulumi** | Manual only (Neon has no Pulumi provider) |
| **Severity** | 🔴 Critical — app won't start without it |

- [ ] Create Neon project (choose Frankfurt region — closest to Vercel fra1)
- [ ] Copy `DATABASE_URL` connection string
- [ ] Set in API deployment (Modal secrets / docker env)

---

## 2. ⚡ Upstash Redis (Queue + Idempotency)

| Item | Detail |
|------|--------|
| **Provider** | [upstash.com](https://upstash.com) |
| **What to do** | Create a Redis instance, get the URL |
| **Env var** | `REDIS_URL` |
| **Where used** | `apps/api/` — job queue, idempotency keys |
| **Pulumi** | Manual only (Upstash has no Pulumi provider) |
| **Severity** | 🔴 Critical — app won't start without it |

- [ ] Create Upstash Redis instance (Frankfurt region)
- [ ] Copy `REDIS_URL` (format: `rediss://default:xxxx@...`)
- [ ] Set in API deployment (Modal secrets / docker env)

---

## 3. 🔐 Clerk (Authentication)

| Item | Detail |
|------|--------|
| **Provider** | [clerk.com](https://clerk.com) |
| **What to do** | Create application, configure webhook |
| **Env vars** | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET` |
| **Where used** | `apps/web/` (frontend auth), `apps/api/` (JWT verification, webhook) |
| **Pulumi** | Manual only (Clerk is dashboard-only) |
| **Severity** | 🔴 Critical — all authenticated endpoints return 401 |

- [ ] Create Clerk application named "aidirector"
- [ ] Copy **Publishable Key** → `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- [ ] Copy **Secret Key** → `CLERK_SECRET_KEY`
- [ ] Configure **Clerk Webhook** → `POST {API_URL}/webhooks/clerk`
      - Subscribe to events: `user.created`, `user.updated`, `organization.created`, `organizationMembership.created`
- [ ] Copy **Webhook signing secret** → `CLERK_WEBHOOK_SECRET`
- [ ] Configure **OAuth providers** (optional): Google, GitHub, etc.
- [ ] Update **redirect URLs** in Clerk Dashboard:
      - Sign in: `{APP_URL}/sign-in`
      - Sign up: `{APP_URL}/sign-up`
      - After sign in: `{APP_URL}/app`
      - After sign up: `{APP_URL}/app`

---

## 4. 📦 Cloudflare R2 (Object Storage)

| Item | Detail |
|------|--------|
| **Provider** | [cloudflare.com](https://cloudflare.com) |
| **What to do** | Create API token, get R2 credentials |
| **Env vars** | `CLOUDFLARE_API_TOKEN` (Pulumi), `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` |
| **Where used** | `infra/` (Pulumi creates bucket), `apps/api/` (uploads + exports) |
| **Pulumi** | ✅ Managed — bucket + CORS created by `pulumi up` |
| **Severity** | 🟡 Warning — uploads and exports fail without it |

### Pulumi setup

- [ ] Create Cloudflare API token with permissions:
      - `R2 Bucket: Read + Write`
      - `Account: Read`
- [ ] Run: `pulumi config set cloudflare:apiToken --secret` (in `infra/`)

### API server env vars

- [ ] Find R2 **Account ID** (Cloudflare dashboard → R2 → Account ID) → `R2_ACCOUNT_ID`
- [ ] Generate R2 **Access Key** (R2 → Manage R2 API Tokens) → `R2_ACCESS_KEY_ID` + `R2_SECRET_ACCESS_KEY`
- [ ] Set `R2_BUCKET` to the bucket name (default: `aidirector-prod`)

---

## 5. ▲ Vercel (Frontend Hosting)

| Item | Detail |
|------|--------|
| **Provider** | [vercel.com](https://vercel.com) |
| **What to do** | Create API token, link to GitHub |
| **Env vars** | `VERCEL_TOKEN` (Pulumi), `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` (GitHub secrets) |
| **Where used** | `infra/` (Pulumi creates project), `.github/workflows/deploy.yml` |
| **Pulumi** | ✅ Managed — project + deployment created by `pulumi up` |
| **Severity** | 🟡 Warning — frontend not deployed |

- [ ] Create Vercel API token (Vercel dashboard → Settings → Tokens)
      - Permissions: Project: Read + Write, Environment Variables: Read + Write
- [ ] Run: `pulumi config set vercel:token --secret` (in `infra/`)
- [ ] After `pulumi up`, note the `VERCEL_PROJECT_ID` and `VERCEL_ORG_ID`
- [ ] Add `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` to GitHub secrets
      (or let Pulumi's GitHub provider do it)

---

## 6. 🤖 GitHub (CI/CD Secrets)

| Item | Detail |
|------|--------|
| **Provider** | github.com |
| **What to do** | Create a fine-grained PAT for Pulumi to set secrets |
| **Env vars** | `GITHUB_TOKEN` (Pulumi) |
| **Where used** | `infra/` (Pulumi sets GitHub Actions secrets) |
| **Pulumi** | ✅ Managed — secrets created by `pulumi up` |
| **Severity** | 🟡 Warning — CI/CD secrets won't be auto-populated |

- [ ] Create GitHub fine-grained PAT with permissions:
      - Repository Actions secrets: Read + Write
- [ ] Run: `pulumi config set github:token --secret` (in `infra/`)
- [ ] After `pulumi up`, all secrets listed in section 11 will be set as GitHub Actions secrets

---

## 7. 🐛 Sentry (Error Tracking)

| Item | Detail |
|------|--------|
| **Provider** | [sentry.io](https://sentry.io) |
| **What to do** | Create project, get DSN + auth token |
| **Env vars** | `NEXT_PUBLIC_SENTRY_DSN`, `SENTRY_DSN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN` |
| **Where used** | `apps/web/` (instrumentation.ts), `apps/api/` |
| **Severity** | 🟢 Optional — app works, errors go unlogged |

- [ ] Create Sentry account / org
- [ ] Create Next.js project → copy DSN → `NEXT_PUBLIC_SENTRY_DSN`
- [ ] Create Python/FastAPI project → copy DSN → `SENTRY_DSN`
- [ ] Create auth token (Sentry Settings → Developer Settings → Auth Tokens)
      - Scope: `project:releases`, `event:read`, `org:read`
- [ ] Note org slug → `SENTRY_ORG`, project slug → `SENTRY_PROJECT`

---

## 8. 💳 Stripe (Billing)

| Item | Detail |
|------|--------|
| **Provider** | [stripe.com](https://stripe.com) |
| **What to do** | Create products + prices, configure webhook |
| **Env vars** | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| **Where used** | `apps/api/` (billing endpoints, webhook) |
| **Pulumi** | Manual only (Stripe products are dashboard-only) |
| **Severity** | 🟡 Warning — billing endpoints fail |

- [ ] Create Stripe account (or use test mode)
- [ ] Create products + prices in Stripe Dashboard
- [ ] Copy **Secret Key** → `STRIPE_SECRET_KEY`
- [ ] Configure **Stripe Webhook** → `POST {API_URL}/webhooks/stripe`
      - Subscribe to events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`
- [ ] Copy **Webhook signing secret** → `STRIPE_WEBHOOK_SECRET`

---

## 9. 🤖 Anthropic (AI / Director Agent)

| Item | Detail |
|------|--------|
| **Provider** | [anthropic.com](https://anthropic.com) |
| **What to do** | Get API key |
| **Env var** | `ANTHROPIC_API_KEY` |
| **Where used** | `apps/api/` (Director Agent plan generation) |
| **Severity** | 🟡 Warning — AI plan generation unavailable |

- [ ] Create Anthropic API key
- [ ] Copy → `ANTHROPIC_API_KEY`

---

## 10. 🚀 Modal (Serverless Workers)

| Item | Detail |
|------|--------|
| **Provider** | [modal.com](https://modal.com) |
| **What to do** | Install CLI, create token, deploy |
| **Env vars** | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` |
| **Where used** | `.github/workflows/deploy.yml`, `apps/api/modal_app.py` |
| **Severity** | 🟡 Warning — background workers not deployed |

- [ ] Install Modal CLI: `pip install modal`
- [ ] Run: `modal token new` — creates `~/.modal.toml` with token
- [ ] Copy token ID + secret → `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET`
- [ ] Create Modal secrets (one per env var group):
      ```bash
      modal secret create aidirector-db DATABASE_URL=...
      modal secret create aidirector-redis REDIS_URL=...
      modal secret create aidirector-r2 R2_ACCOUNT_ID=... R2_ACCESS_KEY_ID=... R2_SECRET_ACCESS_KEY=... R2_BUCKET=...
      modal secret create aidirector-signing PROVENANCE_SIGNING_KEY_B64=...
      modal secret create aidirector-anthropic ANTHROPIC_API_KEY=...
      ```
- [ ] Deploy: `modal deploy apps/api/modal_app.py`

---

## 11. 📋 All Environment Variables — Master List

### 🔴 Critical (app won't start)

| Variable | Source | Set in |
|----------|--------|--------|
| `DATABASE_URL` | Neon Postgres | API env / Modal secret `aidirector-db` |
| `REDIS_URL` | Upstash Redis | API env / Modal secret `aidirector-redis` |
| `CLERK_SECRET_KEY` | Clerk Dashboard | API env + Vercel env + GitHub secret |
| `CLERK_PUBLISHABLE_KEY` | Clerk Dashboard | API env + Vercel env + GitHub secret |
| `CLERK_WEBHOOK_SECRET` | Clerk Dashboard (Webhooks) | API env + GitHub secret |

### 🟡 Warning (degraded but running)

| Variable | Source | Set in |
|----------|--------|--------|
| `R2_ACCOUNT_ID` | Cloudflare R2 Dashboard | API env / Modal secret `aidirector-r2` |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 (API Tokens) | API env / Modal secret `aidirector-r2` |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 (API Tokens) | API env / Modal secret `aidirector-r2` |
| `R2_BUCKET` | Cloudflare R2 (bucket name) | API env / Modal secret `aidirector-r2` |
| `STRIPE_SECRET_KEY` | Stripe Dashboard | API env + GitHub secret |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard (Webhooks) | API env + GitHub secret |
| `ANTHROPIC_API_KEY` | Anthropic Console | API env / Modal secret `aidirector-anthropic` |
| `PROVENANCE_SIGNING_KEY_B64` | Generated (openssl) | API env / Modal secret `aidirector-signing` |
| `VERCEL_TOKEN` | Vercel (Settings → Tokens) | Pulumi + GitHub secret |
| `VERCEL_ORG_ID` | Vercel (team slug) | GitHub secret |
| `VERCEL_PROJECT_ID` | Output of `pulumi up` | GitHub secret |

### 🟢 Optional

| Variable | Source | Set in |
|----------|--------|--------|
| `NEXT_PUBLIC_SENTRY_DSN` | Sentry (Next.js project) | Vercel env + GitHub secret |
| `SENTRY_DSN` | Sentry (Python project) | API env + GitHub secret |
| `SENTRY_ORG` | Sentry (org slug) | Vercel env + GitHub secret |
| `SENTRY_PROJECT` | Sentry (project slug) | Vercel env + GitHub secret |
| `SENTRY_AUTH_TOKEN` | Sentry (Developer Settings) | Vercel env + GitHub secret |
| `LOGFIRE_TOKEN` | Logfire Dashboard | API env |

### Frontend-only (`.env.local` / Vercel)

| Variable | Source |
|----------|--------|
| `NEXT_PUBLIC_API_URL` | API deployment URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk Dashboard |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | `/app` |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | `/app` |

---

## 12. ▶️ Deployment Sequence

After all keys are collected, do this in order:

```bash
# 1. Pulumi — create cloud resources + GitHub secrets
cd infra
pulumi config set cloudflare:apiToken --secret     # Cloudflare API token
pulumi config set vercel:token --secret             # Vercel token
pulumi config set github:token --secret             # GitHub PAT
pulumi up                                           # Creates: R2 bucket, Vercel project, GH secrets

# 2. Modal — deploy backend workers
cd apps/api
modal secret create aidirector-db DATABASE_URL=...           # Neon
modal secret create aidirector-redis REDIS_URL=...           # Upstash
modal secret create aidirector-r2 R2_ACCOUNT_ID=...  ...     # Cloudflare R2
modal secret create aidirector-signing PROVENANCE_SIGNING_KEY_B64=...
modal secret create aidirector-anthropic ANTHROPIC_API_KEY=...
modal deploy apps/api/modal_app.py

# 3. Push to main → GitHub Actions deploys frontend to Vercel
git push origin main

# 4. Configure webhooks
#    Clerk → POST {API_URL}/webhooks/clerk
#    Stripe → POST {API_URL}/webhooks/stripe
```
