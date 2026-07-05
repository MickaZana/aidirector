import path from "node:path";
import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const isDev = process.env.NODE_ENV === "development";

const cspDirectives = [
  "default-src 'self'",
  // Scripts: allow self + Next.js inline chunks + Clerk hosted JS
  isDev
    ? "script-src 'self' 'unsafe-eval' 'unsafe-inline' https://clerk.com https://*.clerk.accounts.dev"
    : "script-src 'self' 'unsafe-inline' https://clerk.com https://*.clerk.accounts.dev",
  // Styles: allow self + inline (Tailwind inlines critical CSS)
  "style-src 'self' 'unsafe-inline'",
  // Images: allow self + data URIs + Clerk avatar CDN + R2 public bucket
  "img-src 'self' data: blob: https://*.clerk.com https://*.cloudflare.com",
  // Fonts: self only
  "font-src 'self'",
  // Connect: API + Clerk + Sentry + Stripe
  [
    "connect-src 'self'",
    "https://clerk.com https://*.clerk.accounts.dev",
    "https://sentry.io https://*.ingest.sentry.io",
    "https://api.stripe.com",
    isDev ? "ws://localhost:*" : "",
  ]
    .filter(Boolean)
    .join(" "),
  // Frames: Stripe payment element only
  "frame-src https://js.stripe.com https://hooks.stripe.com",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "upgrade-insecure-requests",
].join("; ");

const securityHeaders = [
  { key: "X-DNS-Prefetch-Control", value: "on" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Content-Security-Policy", value: cspDirectives },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  typedRoutes: true,
  compress: true,
  poweredByHeader: false,
  // Pin the file-tracing root to apps/web so the monorepo lockfile at the
  // repo root doesn't drag Next.js up a level (was causing /_next route 404s).
  outputFileTracingRoot: path.resolve(__dirname),

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  silent: !process.env.CI,
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  widenClientFileUpload: true,
  sourcemaps: { disable: false },
  // Replaces deprecated `disableLogger` — treeshake debug logs at build time
  webpack: {
    treeshake: {
      removeDebugLogging: true,
    },
    automaticVercelMonitors: false,
  },
});
