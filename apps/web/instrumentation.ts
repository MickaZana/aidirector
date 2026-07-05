/**
 * Sentry server-side initialization.
 *
 * Replaces the deprecated sentry.server.config.ts and sentry.edge.config.ts
 * patterns. Next.js calls the `register()` export once during server startup.
 *
 * https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/#create-initialization-config-files
 */
import * as Sentry from "@sentry/nextjs";

export async function register() {
  Sentry.init({
    dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
    tracesSampleRate: 0.05,
    environment: process.env.NODE_ENV,
  });
}

export const onRequestError = Sentry.captureRequestError;
