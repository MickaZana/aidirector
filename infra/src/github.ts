/**
 * GitHub Actions secrets for CI/CD.
 *
 * Requires:
 *   pulumi config set github:token --secret
 *
 * The GitHub token needs permissions:
 *   - Repository Actions secrets: Read + Write
 */

import * as github from "@pulumi/github";
import * as pulumi from "@pulumi/pulumi";
import { CloudflareResources } from "./cloudflare";
import { VercelResources } from "./vercel";

export interface GithubResources {
  secrets: pulumi.Output<Record<string, string>>;
}

export function createGithubResources(
  config: pulumi.Config,
  r2: CloudflareResources,
  vercelResources: VercelResources,
): GithubResources {
  const repository = config.require("github_repository");

  // Secrets to set in GitHub Actions
  const secretDefs = [
    { name: "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", value: process.env.CLERK_PUBLISHABLE_KEY || "" },
    { name: "CLERK_SECRET_KEY", value: process.env.CLERK_SECRET_KEY || "" },
    { name: "CLERK_WEBHOOK_SECRET", value: process.env.CLERK_WEBHOOK_SECRET || "" },
    { name: "SENTRY_DSN", value: process.env.SENTRY_DSN || "" },
    { name: "SENTRY_ORG", value: process.env.SENTRY_ORG || "" },
    { name: "SENTRY_PROJECT", value: process.env.SENTRY_PROJECT || "" },
    { name: "SENTRY_AUTH_TOKEN", value: process.env.SENTRY_AUTH_TOKEN || "" },
    { name: "STRIPE_SECRET_KEY", value: process.env.STRIPE_SECRET_KEY || "" },
    { name: "STRIPE_WEBHOOK_SECRET", value: process.env.STRIPE_WEBHOOK_SECRET || "" },
    { name: "ANTHROPIC_API_KEY", value: process.env.ANTHROPIC_API_KEY || "" },
    { name: "MODAL_TOKEN_ID", value: process.env.MODAL_TOKEN_ID || "" },
    { name: "MODAL_TOKEN_SECRET", value: process.env.MODAL_TOKEN_SECRET || "" },
    { name: "R2_ACCOUNT_ID", value: process.env.R2_ACCOUNT_ID || "" },
    { name: "R2_ACCESS_KEY_ID", value: process.env.R2_ACCESS_KEY_ID || "" },
    { name: "R2_SECRET_ACCESS_KEY", value: process.env.R2_SECRET_ACCESS_KEY || "" },
    { name: "PROVENANCE_SIGNING_KEY_B64", value: process.env.PROVENANCE_SIGNING_KEY_B64 || "" },
    { name: "VERCEL_TOKEN", value: process.env.VERCEL_TOKEN || "" },
    { name: "VERCEL_ORG_ID", value: process.env.VERCEL_ORG_ID || "" },
    { name: "VERCEL_PROJECT_ID", value: process.env.VERCEL_PROJECT_ID || "" },
  ];

  for (const s of secretDefs) {
    if (s.value) {
      new github.ActionsSecret(`aidirector-secret-${s.name.toLowerCase().replace(/_/g, "-")}`, {
        repository: repository,
        secretName: s.name,
        plaintextValue: s.value,
      });
    }
  }

  return {
    secrets: pulumi.output({}),
  };
}
