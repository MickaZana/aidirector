# Beta Operations Dashboard

## Architecture

The internal route is `/app/admin/beta-dashboard`. It is covered by the existing authenticated `/app/*` middleware and performs a second client-side authorization check against Clerk `publicMetadata.role === "admin"` (or `publicMetadata.isAdmin === true`). Non-administrators receive a 403 view.

The dashboard reads the existing first-party `analytics` service. It does not add an external analytics provider. The current provider stores privacy-conscious, non-PII events in browser `localStorage`; metrics that require server aggregation are deliberately displayed as `—` until the provider gains a backend sink.

## Data sources and definitions

- Upload metrics: `upload_started`, `upload_completed`, and `upload_failed`.
- Processing metrics: `processing_started`, `processing_completed`, `processing_failed`, and `cancel_processing_used`.
- Clip metrics: preview, download, download-all, share, and copy-link events.
- Stability: failure, network, offline, and CSP events. CSP violations are shown as zero after the policy fix; a Reporting API sink should replace this placeholder before a large beta.
- Funnel: event counts divided by the preceding stage count.
- Readiness: average of upload success, processing success, crash/stability proxy, feedback baseline, and performance/offline proxy. Missing server-backed data is surfaced rather than fabricated.

## Refresh and export

Refresh rereads the analytics provider. CSV exports the event ledger; JSON exports the event ledger plus the derived metric snapshot. Both exports are generated locally in the browser.

## Future integrations

The provider should eventually flush to a first-party, tenant-scoped analytics endpoint. That endpoint can supply invited users, unique active users, sessions, ratings, comments, LCP, runtime errors, and precise processing durations without changing the dashboard component contract.

## Verification

- CSP now explicitly allows Clerk's worker execution only from `self` and `blob:` and includes the Clerk connection/frame hosts required by the existing integration.
- Frontend unit tests, TypeScript, and production build should be run from the repository root.
- Browser console verification requires an available browser backend; the Codex Browser runtime was unavailable during implementation.
