/**
 * Sentry client-side initialization.
 *
 * This file is loaded on the client at runtime, replacing the deprecated
 * sentry.client.config.ts pattern.
 *
 * https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/#create-initialization-config-files
 */
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.05,
  environment: process.env.NEXT_PUBLIC_VERCEL_ENV || process.env.NODE_ENV || "development",
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
