# Security Checklist — Beta Operations

## Overview

Security verification for the AI Director beta launch. Each item must be verified before and during beta operations. Items marked **[MANUAL]** require human verification. Items marked **[AUTOMATED]** are gated by CI or monitoring.

---

## 1. Authentication & Authorization

- [x] Clerk JWT RS256 verification enforced on all `/app/*` routes (middleware.ts)
- [x] Tenant isolation via `tenant_id` in all SQLAlchemy queries
- [x] API JWT verification on all protected endpoints
- [x] No hardcoded credentials in source code
- [x] CORS restricted to known origins (`ALLOWED_ORIGINS` env var)
- [x] Auth tokens transmitted only via `Authorization: Bearer` header (never in URLs)

**Verification:**
- [ ] **[MANUAL]** Attempt to access `/app/*` without auth → should redirect to sign-in
- [ ] **[MANUAL]** Attempt API call without JWT → should return 401
- [ ] **[MANUAL]** Attempt API call with expired JWT → should return 401
- [ ] **[AUTOMATED]** CI enforces no secrets in code (if secret scanning configured)

---

## 2. Content Security Policy (CSP)

Current CSP headers (next.config.ts):

```
default-src 'self'
script-src 'self' 'unsafe-inline' https://clerk.com https://*.clerk.accounts.dev
style-src 'self' 'unsafe-inline'
img-src 'self' data: blob: https://*.clerk.com https://*.cloudflare.com
font-src 'self'
connect-src 'self' https://clerk.com https://*.clerk.accounts.dev https://sentry.io https://*.ingest.sentry.io https://api.stripe.com
frame-src https://js.stripe.com https://hooks.stripe.com
object-src 'none'
base-uri 'self'
form-action 'self'
upgrade-insecure-requests
```

**Verification:**
- [ ] **[MANUAL]** No `unsafe-eval` in production (removed via NODE_ENV check)
- [ ] **[MANUAL]** All external resources allowed by CSP (Clerk, Sentry, Stripe)
- [ ] **[MANUAL]** CSP headers present on all pages (check browser DevTools → Network)
- [ ] **[AUTOMATED]** `upgrade-insecure-requests` forces HTTPS

---

## 3. HTTP Security Headers

- [x] `X-DNS-Prefetch-Control: on`
- [x] `X-Frame-Options: DENY` (prevents clickjacking)
- [x] `X-Content-Type-Options: nosniff`
- [x] `Referrer-Policy: strict-origin-when-cross-origin`
- [x] `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- [x] `Content-Security-Policy` (see above)
- [x] `X-Powered-By` header disabled (`poweredByHeader: false`)

**Verification:**
- [ ] **[MANUAL]** All security headers present in production responses
- [ ] **[MANUAL]** No sensitive headers leaked (server info, framework version)

---

## 4. Data Protection

- [x] No PII stored client-side (analytics uses only localStorage, no cookies)
- [x] All analytics data is non-personal (event names, file sizes, no user IDs)
- [x] Uploads stored in R2 with tenant-prefixed keys (`tenant/{tenant_id}/upload/{upload_id}/`)
- [x] Presigned URLs for uploads (time-limited, scoped to specific keys)
- [x] GDPR DSR endpoints implemented (deletion, export, status)
- [x] Provenance signing (Ed25519) for all exported clips

**Verification:**
- [ ] **[MANUAL]** Analytics data contains no PII (verify event properties)
- [ ] **[MANUAL]** Presigned URLs expire after upload timeout
- [ ] **[MANUAL]** R2 bucket is not publicly listable
- [ ] **[AUTOMATED]** DSR deletion flow: request → grace period → permanent delete

---

## 5. Rate Limiting & Abuse Prevention

- [x] API rate limiting implemented (429 with `Retry-After` header)
- [x] Frontend rate-limit listener dispatches toast + cooldown
- [x] CORS whitelist restricts API access to known origins
- [x] Upload size limits enforced client-side and server-side
- [x] File type validation (MIME type whitelist)

**Verification:**
- [ ] **[MANUAL]** Rapid API calls → 429 response
- [ ] **[MANUAL]** Invalid file type upload → rejected
- [ ] **[MANUAL]** Upload > 3 GB → rejected client-side
- [ ] **[AUTOMATED]** Rate limit events dispatched from ApiClient

---

## 6. Dependency & Supply Chain

- [x] `frozen-lockfile` in CI (prevents untracked dependency changes)
- [x] pnpm lockfile committed (integrity guarantees)
- [x] No deprecated packages with known vulnerabilities (regular audit)

**Verification:**
- [ ] **[AUTOMATED]** `pnpm audit` passes (no critical vulnerabilities)
- [ ] **[AUTOMATED]** CI fails on dependency changes without lockfile update
- [ ] **[MANUAL]** Review `pnpm-lock.yaml` for unexpected changes before merge

---

## 7. Infrastructure Security

- [x] Database credentials not hardcoded (sourced from env vars)
- [x] Redis with TLS (`rediss://`)
- [x] Neon Postgres with SSL enforced
- [x] R2 with per-object access controls (presigned URLs)
- [x] Stripe webhooks verified via signature
- [x] Clerk webhooks verified via Svix signature
- [x] `.env*` files in `.gitignore` (except `.env.example`)
- [x] `.next` and `node_modules` in `.gitignore`

**Verification:**
- [ ] **[MANUAL]** No secrets in git history (check with `git log --diff-filter=A -- '*.env*'`)
- [ ] **[MANUAL]** Database firewall restricts access to known IPs
- [ ] **[MANUAL]** Redis ACL/credentials not using defaults

---

## 8. Error Handling & Information Disclosure

- [x] Custom error boundary (`error.tsx`) — no stack traces exposed to users
- [x] Global error boundary (`global-error.tsx`) — minimal info in critical failures
- [x] 404 pages render without exposure of routes/structure
- [x] API errors return structured JSON (no raw exceptions)
- [x] Sentry captures errors server-side and client-side

**Verification:**
- [ ] **[MANUAL]** Trigger a 404 → no stack trace visible
- [ ] **[MANUAL]** Navigate to invalid route → friendly error page
- [ ] **[AUTOMATED]** Sentry error grouping configured

---

## 9. Logging & Monitoring

- [x] Sentry error tracking (frontend + backend)
- [x] Structured console logging in development
- [x] Rate-limit events logged
- [x] Billing-limit events logged
- [x] Health check endpoints non-sensitive (no data exposure)

**Verification:**
- [ ] **[MANUAL]** Sentry receives events in production
- [ ] **[MANUAL]** No sensitive data in log output (passwords, tokens, PII)
- [ ] **[AUTOMATED]** Health endpoints return 200 without exposing internals

---

## 10. GDPR & Compliance

- [x] Privacy page published (`/privacy`)
- [x] Terms of service published (`/terms`)
- [x] Data deletion request endpoint (DSR)
- [x] Data export endpoint (GDPR Article 20)
- [x] 30-day grace period before permanent deletion
- [x] Consent: no tracking cookies, analytics opt-out available

**Verification:**
- [ ] **[MANUAL]** Privacy page covers data collection, storage, retention, deletion
- [ ] **[MANUAL]** Terms page covers acceptable use, liability, termination
- [ ] **[MANUAL]** DSR flow: request → confirm → wait → delete
- [ ] **[MANUAL]** Analytics opt-out: `analytics.setEnabled(false)`

---

## Summary

| Category | Items | Verified |
|----------|-------|----------|
| Auth & AuthZ | 4 | — |
| CSP | 4 | — |
| HTTP Security Headers | 7 | — |
| Data Protection | 6 | — |
| Rate Limiting | 4 | — |
| Dependencies | 3 | — |
| Infrastructure | 8 | — |
| Error Handling | 4 | — |
| Logging & Monitoring | 4 | — |
| GDPR & Compliance | 6 | — |
| **Total** | **50** | **—** |

**Sign-off required before beta launch:**
```
Security verified by: _______________
Date: ______________________________
```
