"use client";

/**
 * Enhanced empty state for the Renders page.
 *
 * When there's a job but no renders yet, shows the pipeline timeline
 * so the user can see how far along the processing is. When there are
 * no jobs at all, shows the standard CTA.
 */
import { motion } from "framer-motion";
import { FileVideo, Upload } from "lucide-react";
import { Button } from "@/design-system/Button";
import { Badge } from "@/design-system/Badge";
import { ProcessingTimeline } from "@/features/processing-timeline/ProcessingTimeline";

interface RendersEmptyStateProps {
  /** If a job exists, show its pipeline progress. */
  jobId?: string | null;
}

export function RendersEmptyState({ jobId }: RendersEmptyStateProps) {
  // A job exists — show pipeline progress
  if (jobId) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.2, 0.8, 0.2, 1] }}
        className="max-w-2xl mx-auto"
      >
        <div className="text-center mb-6 space-y-2">
          <Badge tone="accent" pulse>Pipeline in progress</Badge>
          <h2 className="text-xl font-semibold tracking-tight mt-3">No renders yet</h2>
          <p className="text-sm text-[color:var(--color-text-secondary)]">
            Renders appear here once the pipeline finishes analysis, ranking, and directing.
            Here&apos;s where things stand:
          </p>
        </div>
        <ProcessingTimeline jobId={jobId} />
      </motion.div>
    );
  }

  // No job at all — show generic CTA
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex flex-col items-center justify-center h-[60vh] gap-6"
    >
      <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-[color:var(--color-accent-green)]/15 to-[color:var(--color-accent-blue)]/10 border border-[color:var(--color-border-accent)] flex items-center justify-center shadow-[0_0_80px_-20px_rgba(0,230,161,0.3)]">
        <FileVideo className="h-10 w-10 text-[color:var(--color-accent-green)]" strokeWidth={1.5} />
      </div>

      <div className="text-center max-w-sm space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">No render jobs yet</h2>
        <p className="text-sm text-[color:var(--color-text-secondary)] leading-relaxed">
          Start by uploading a match. The pipeline produces platform-ready renders
          in 9:16, 1:1, and 16:9 — captioned, cropped, and watermarked.
        </p>
      </div>

      <a href="/app/upload">
        <Button variant="primary" size="lg">
          <Upload className="h-4 w-4" />
          Upload a match
        </Button>
      </a>
    </motion.div>
  );
}
