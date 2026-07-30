"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  PageContainer,
  Typography,
  Button,
  Card,
  EmptyState,
  AppIcon,
} from "@/features/design-system";
import { analytics } from "@/services/analytics";
import { ClipCard } from "@/features/my-clips/components/ClipCard";
import { ProjectSummaryCard } from "@/features/my-clips/components/ProjectSummaryCard";
import { PreviewPanel } from "@/features/my-clips/components/PreviewPanel";
import { FeedbackWidget } from "@/features/feedback";
import type { Clip, Project } from "@/features/my-clips/types";

// ── Mock Data ──────────────────────────────────────────────

const MOCK_PROJECT: Project = {
  videoName: "Liverpool vs Chelsea — Full Match",
  uploadDate: "28 Jul 2026",
  clipCount: 12,
  processingTime: "3m 42s",
  platforms: ["youtube_shorts", "tiktok", "instagram_reels"],
};

const MOCK_CLIPS: Clip[] = [
  {
    id: "clip-1",
    title: "Goal 78' — Salah",
    duration: "0:45",
    score: 9.8,
    platforms: ["youtube_shorts", "tiktok"],
    status: "ready",
    createdAt: "28 Jul 2026",
  },
  {
    id: "clip-2",
    title: "Penalty Save 52'",
    duration: "0:32",
    score: 9.5,
    platforms: ["youtube_shorts", "instagram_reels"],
    status: "ready",
    createdAt: "28 Jul 2026",
  },
  {
    id: "clip-3",
    title: "Post-Match Analysis",
    duration: "1:15",
    score: 9.2,
    platforms: ["youtube_shorts", "tiktok", "instagram_reels"],
    status: "ready",
    createdAt: "28 Jul 2026",
  },
  {
    id: "clip-4",
    title: "Fan Reaction 63'",
    duration: "0:28",
    score: 8.9,
    platforms: ["tiktok"],
    status: "ready",
    createdAt: "28 Jul 2026",
  },
  {
    id: "clip-5",
    title: "Half-Time Highlights",
    duration: "1:02",
    score: 8.7,
    platforms: ["youtube_shorts", "instagram_reels"],
    status: "ready",
    createdAt: "28 Jul 2026",
  },
  {
    id: "clip-6",
    title: "Defensive Stand 34'",
    duration: "0:38",
    score: 8.5,
    platforms: ["youtube_shorts"],
    status: "ready",
    createdAt: "28 Jul 2026",
  },
];

/**
 * My Clips page — Screen 3 of the 3-screen creator-first experience.
 *
 * Answers three questions immediately:
 *   1. Which clips are ready?
 *   2. Which are the best? (quality score badges)
 *   3. How do I download or share them?
 *
 * Accessibility:
 * - Keyboard navigation throughout the gallery
 * - Focus management for the preview panel (via BottomSheet)
 * - Screen reader labels on all action buttons
 */
export default function MyClipsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [selectedClip, setSelectedClip] = useState<Clip | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  // Check for success param from processing page redirect
  useEffect(() => {
    const fromProcessing = searchParams.get("success") === "true";
    if (fromProcessing) {
      setShowSuccess(true);
      // Auto-dismiss after 5 seconds
      const timer = setTimeout(() => setShowSuccess(false), 5000);
      // Clean up the URL
      window.history.replaceState(null, "", "/app/clips");
      return () => clearTimeout(timer);
    }
  }, [searchParams]);

  // ── Handlers ──────────────────────────────────────────────

  const handlePreview = useCallback((clip: Clip) => {
    setSelectedClip(clip);
    analytics.track("clip_preview_opened", { clipId: clip.id, clipTitle: clip.title });
  }, []);

  const handleClosePreview = useCallback(() => {
    setSelectedClip(null);
  }, []);

  const handleDownload = useCallback((clip: Clip) => {
    analytics.track("download_clicked", { clipId: clip.id, clipTitle: clip.title });
    // Placeholder: wire up actual download
    console.log("Downloading clip:", clip.id);
  }, []);

  const handleDownloadAll = useCallback(() => {
    analytics.track("download_all_clicked", { clipCount: MOCK_CLIPS.length });
    // Placeholder: wire up bulk download
    console.log("Downloading all clips");
  }, []);

  // ── Empty state support ────────────────────────────────────
  // When MOCK_CLIPS is replaced with real data, set `empty` to true
  // when no clips exist. For now, you can test by appending `?empty=1` to the URL.
  const isEmpty = searchParams.get("empty") === "1" || MOCK_CLIPS.length === 0;

  // ── Render: Empty State ───────────────────────────────────
  if (isEmpty) {
    return (
      <PageContainer>
        <EmptyState
          icon={AppIcon}
          title="No clips yet"
          description="Upload your first video to generate AI-powered clips. We'll find the best moments and create social-ready clips automatically."
          action={
            <Button
              size="lg"
              variant="primary"
              onClick={() => router.push("/app/upload" as never)}
            >
              <AppIcon name="upload" size="md" />
              Create Your First Project
            </Button>
          }
        />
      </PageContainer>
    );
  }

  // ── Render: Clips Gallery ─────────────────────────────────
  return (
    <PageContainer>
      {/* Success Banner */}
      {showSuccess && (
        <div
          className="flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 mb-8 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-2 duration-250"
          role="status"
          aria-live="polite"
        >
          <span className="text-2xl" aria-hidden="true">
            🎉
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-emerald-900">
              Your clips are ready!
            </p>
            <p className="text-sm text-emerald-700">
              All {MOCK_CLIPS.length} clips have been generated and optimised for your selected
              platforms.
            </p>
          </div>
          <button
            onClick={() => setShowSuccess(false)}
            className="shrink-0 rounded-lg p-1.5 text-emerald-600 hover:bg-emerald-100 transition-colors"
            aria-label="Dismiss"
          >
            <AppIcon name="x" size="sm" />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <Typography variant="hero" className="text-slate-900">
            My Clips
          </Typography>
          <Typography variant="subtitle" className="mt-1">
            Your AI-generated clips are ready.
          </Typography>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Button
            variant="primary"
            size="lg"
            onClick={handleDownloadAll}
          >
            <AppIcon name="download" size="md" />
            Download All
          </Button>
          <Button
            variant="secondary"
            size="lg"
            onClick={() => router.push("/app/upload" as never)}
          >
            <AppIcon name="upload" size="md" />
            Create Another Project
          </Button>
        </div>
      </div>

      {/* Project Summary */}
      <ProjectSummaryCard project={MOCK_PROJECT} className="mb-10" />

      {/* Clip Gallery */}
      <div>
        <Typography
          variant="sectionTitle"
          className="mb-6"
        >
          Clips
        </Typography>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {MOCK_CLIPS.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              onPreview={handlePreview}
              onDownload={handleDownload}
            />
          ))}
        </div>
      </div>

      {/* Preview Panel (BottomSheet) */}
      <PreviewPanel
        clip={selectedClip}
        onClose={handleClosePreview}
        onDownload={handleDownload}
      />

      {/* In-app feedback widget — visible when clips are present */}
      {!isEmpty && <FeedbackWidget />}
    </PageContainer>
  );
}
