/**
 * AI Director — Infrastructure-as-Code (Pulumi)
 *
 * Manages cloud resources that have provisioning APIs:
 *   - Cloudflare R2 bucket (object storage for uploads + renders)
 *   - Vercel project (Next.js frontend deployment)
 *   - GitHub Actions secrets (CI/CD env vars)
 *
 * Resources that require manual setup (documented in README):
 *   - Neon Postgres (no public provisioning API)
 *   - Upstash Redis (no public provisioning API)
 *   - Clerk app & webhooks (dashboard-only)
 *   - Stripe products & webhooks (dashboard-only)
 *   - Modal token & deployment (CLI-only)
 */

import * as pulumi from "@pulumi/pulumi";
import { createCloudflareResources } from "./cloudflare";
import { createVercelResources } from "./vercel";
import { createGithubResources } from "./github";

const config = new pulumi.Config("aidirector-infra");
const environment = config.require("environment");

// ── Stack exports ──────────────────────────────────────────────────────────
export const stackEnvironment = environment;

// ── Cloudflare R2 ──────────────────────────────────────────────────────────
const r2 = createCloudflareResources(config);
export const r2BucketName = r2.bucketName;
export const r2PublicUrl = r2.publicUrl;

// ── Vercel project ─────────────────────────────────────────────────────────
const vercel = createVercelResources(config);
export const vercelProjectId = vercel.projectId;
export const vercelDomains = vercel.domains;

// ── GitHub Actions secrets ─────────────────────────────────────────────────
const github = createGithubResources(config, r2, vercel);
export const githubSecrets = github.secrets;
