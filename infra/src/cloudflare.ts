/**
 * Cloudflare R2 resources.
 *
 * Requires:
 *   pulumi config set cloudflare:apiToken --secret
 *
 * The API token needs permissions:
 *   - R2 Bucket: Read + Write
 *   - Account: Read
 */

import * as cloudflare from "@pulumi/cloudflare";
import * as pulumi from "@pulumi/pulumi";

export interface CloudflareResources {
  bucketName: pulumi.Output<string>;
  publicUrl: pulumi.Output<string>;
}

export function createCloudflareResources(config: pulumi.Config): CloudflareResources {
  const bucketName = config.require("r2_bucket_name");
  const publicUrl = config.get("r2_public_url") ?? `https://${bucketName}.r2.cloudflarestorage.com`;

  // R2 bucket for uploads and rendered outputs
  const bucket = new cloudflare.R2Bucket("aidirector-media", {
    name: bucketName,
    location: "WEUR", // Western Europe — closest to Neon (Frankfurt) + Upstash (Frankfurt)
    // CORS rules allowing the API server to PUT objects
    corsRules: [{
      allowedOrigins: ["*"], // Restricted by presigned URL
      allowedMethods: ["GET", "PUT", "HEAD"],
      allowedHeaders: ["*"],
      maxAgeSeconds: 3600,
    }],
  });

  // Lifecycle policy — auto-delete objects after 90 days (unless retained for export)
  // Applied via Cloudflare dashboard because R2 lifecycle rules are not yet in the
  // Pulumi Cloudflare provider as of v5.x. Uncomment when available:
  //
  // new cloudflare.R2BucketLifecycle("aidirector-media-lifecycle", {
  //   bucketId: bucket.id,
  //   rules: [{
  //     id: "auto-expire",
  //     status: "enabled",
  //     expiration: { days: 90 },
  //   }],
  // });

  return {
    bucketName: bucket.id,
    publicUrl: pulumi.output(publicUrl),
  };
}
