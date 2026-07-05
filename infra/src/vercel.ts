/**
 * Vercel project for Next.js frontend.
 *
 * Requires:
 *   pulumi config set vercel:token --secret
 *
 * The Vercel token needs permissions:
 *   - Project: Read + Write
 *   - Environment Variables: Read + Write
 */

import * as vercel from "@pulumi/vercel";
import * as pulumi from "@pulumi/pulumi";

export interface VercelResources {
  projectId: pulumi.Output<string>;
  domains: pulumi.Output<string[]>;
}

export function createVercelResources(config: pulumi.Config): VercelResources {
  const projectName = config.require("vercel_project_name");
  const framework = "nextjs";

  // Vercel project
  const project = new vercel.Project("aidirector-web", {
    name: projectName,
    framework: framework,
    rootDirectory: "apps/web",
    gitRepository: {
      type: "github",
      repo: config.require("github_repository"),
      productionBranch: "main",
    },
    buildCommand: "pnpm build",
    outputDirectory: ".next",
    installCommand: "pnpm install --frozen-lockfile",
    serverlessFunctionRegion: "fra1", // Frankfurt — close to Neon Postgres
  });

  // Production environment variables
  const envVars: { key: string; value: string; target: string[] }[] = [
    { key: "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", value: process.env.CLERK_PUBLISHABLE_KEY || "", target: ["production", "preview"] },
    { key: "CLERK_SECRET_KEY", value: process.env.CLERK_SECRET_KEY || "", target: ["production", "preview"] },
    { key: "NEXT_PUBLIC_API_URL", value: process.env.API_BASE_URL || "https://api.aidirector.io", target: ["production"] },
    { key: "NEXT_PUBLIC_SENTRY_DSN", value: process.env.NEXT_PUBLIC_SENTRY_DSN || "", target: ["production", "preview"] },
    { key: "SENTRY_ORG", value: process.env.SENTRY_ORG || "", target: ["production"] },
    { key: "SENTRY_PROJECT", value: process.env.SENTRY_PROJECT || "", target: ["production"] },
  ];

  for (const ev of envVars) {
    if (ev.value) {
      new vercel.ProjectEnvironmentVariable(`aidirector-env-${ev.key.toLowerCase()}`, {
        projectId: project.id,
        key: ev.key,
        value: ev.value,
        targets: ev.target,
      });
    }
  }

  // Default domain from Vercel
  const deployment = new vercel.Deployment("aidirector-web-deploy", {
    projectId: project.id,
    production: true,
    ref: "main",
  });

  return {
    projectId: project.id,
    domains: pulumi.all([deployment.url]).apply(urls => urls),
  };
}
