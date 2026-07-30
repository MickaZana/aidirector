"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { LogoMark } from "@/components/brand/LogoMark";
import { analytics } from "@/services/analytics";
import {
  PageContainer,
  Card,
  Typography,
  Button,
  ProgressIndicator,
  ProgressTimeline,
  ConfirmationDialog,
  AppIcon,
} from "@/features/design-system";
import type { TimelineStage } from "@/features/design-system";

// ── Constants ──────────────────────────────────────────────

/** Activity messages — rotate through these during processing */
const ACTIVITY_MESSAGES = [
  "Watching your video",
  "Finding key moments",
  "Creating captions",
  "Preparing vertical clips",
  "Getting everything ready for download",
] as const;

/** Helpful tips shown while the user waits */
const TIPS = [
  "You can safely leave this page—we'll keep working.",
  "Longer matches naturally take a little more time.",
  "Your original video is never modified.",
] as const;

/** Processing stages for the "What's Happening?" timeline */
const PROCESSING_STAGES: TimelineStage[] = [
  { id: "upload", label: "Upload Complete", threshold: 0 },
  { id: "watching", label: "AI Watching Your Video", threshold: 20 },
  { id: "finding", label: "Finding Key Moments", threshold: 40 },
  { id: "creating", label: "Creating Clips", threshold: 65 },
  { id: "preparing", label: "Preparing Downloads", threshold: 85 },
];

/** Simulated total processing time in milliseconds (~3 min for a 90-min match) */
const SIMULATED_DURATION = 180_000;

/** If processing takes more than this multiple of expected duration, show timeout */
const TIMEOUT_THRESHOLD = SIMULATED_DURATION * 1.5;

/** How often progress updates (ms) */
const PROGRESS_INTERVAL = 250;

/** How long each activity message displays (ms) */
const ACTIVITY_INTERVAL = 4000;

/** How long each tip displays (ms) */
const TIP_INTERVAL = 8000;

// ── Helpers ────────────────────────────────────────────────

function formatTimeRemaining(ms: number): string {
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

// ── Page Component ─────────────────────────────────────────

/**
 * Processing screen — Screen 2 of the 3-screen creator-first experience.
 *
 * Replaces a generic spinner with a calm, guided experience that builds
 * user confidence while AI processes their video.
 *
 * Accessibility:
 * - Progress announcements via aria-live regions
 * - Respects reduced-motion preferences
 * - Full keyboard navigation
 * - Focus trap in confirmation dialog
 */
export default function ProcessingPage() {
  const router = useRouter();

  // Progress state
  const [progress, setProgress] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [startTime] = useState(Date.now());

  // Activity message index
  const [activityIndex, setActivityIndex] = useState(0);

  // Tip index
  const [tipIndex, setTipIndex] = useState(0);

  // Cancel dialog
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  // Completion state
  const [completed, setCompleted] = useState(false);

  // Timeout detection
  const [takingLonger, setTakingLonger] = useState(false);

  // Ref to track if component is still mounted
  const mountedRef = useRef(true);

  // ── Simulated progress ──────────────────────────────────
  useEffect(() => {
    // In production, this would poll a backend endpoint
    const interval = setInterval(() => {
      if (!mountedRef.current) return;

      const now = Date.now();
      const elapsedMs = now - startTime;
      setElapsed(elapsedMs);

      // Calculate progress using ease-out curve for natural feel
      const rawProgress = Math.min(100, (elapsedMs / SIMULATED_DURATION) * 100);
      // Apply easing for smoother feel at start and end
      const eased = rawProgress < 5
        ? rawProgress // Linear start
        : rawProgress > 90
          ? 90 + (rawProgress - 90) * 0.5 // Slow down near end
          : rawProgress;

      const clamped = Math.min(100, Math.max(0, eased));
      setProgress(clamped);

      if (clamped >= 100) {
        clearInterval(interval);
        setCompleted(true);
        analytics.track("processing_completed");
      }
    }, PROGRESS_INTERVAL);

    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [startTime]);

  // ── Timeout detection ─────────────────────────────────────
  useEffect(() => {
    if (completed || takingLonger) return;
    const timer = setTimeout(() => {
      setTakingLonger(true);
    }, TIMEOUT_THRESHOLD);
    return () => clearTimeout(timer);
  }, [completed, takingLonger]);

  // ── Rotate activity messages ────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      setActivityIndex((prev) => (prev + 1) % ACTIVITY_MESSAGES.length);
    }, ACTIVITY_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  // ── Rotate tips ─────────────────────────────────────────
  useEffect(() => {
    const interval = setInterval(() => {
      setTipIndex((prev) => (prev + 1) % TIPS.length);
    }, TIP_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  // ── Cancel handler ──────────────────────────────────────
  const handleCancelConfirm = useCallback(() => {
    setCancelling(true);
    analytics.track("cancel_processing_used");
    // Simulate cancellation — redirect back to upload with cancelled param
    setTimeout(() => {
      router.push("/app/upload?cancelled=true" as never);
    }, 800);
  }, [router]);

  // ── Completed: redirect to clips ────────────────────────
  useEffect(() => {
    if (completed) {
      const timer = setTimeout(() => {
        if (mountedRef.current) {
          router.push("/app/clips?success=true" as never);
        }
      }, 2500);
      return () => clearTimeout(timer);
    }
  }, [completed, router]);

  // ── Estimated time remaining ────────────────────────────
  const remaining = SIMULATED_DURATION - elapsed;
  const eta = formatTimeRemaining(remaining);

  // ── Render ──────────────────────────────────────────────
  return (
    <PageContainer className="flex flex-col items-center justify-center min-h-[calc(100vh-8rem)]">
      {/* Logo + heading */}
      <div className="flex flex-col items-center mb-12">
        <LogoMark className="h-12 w-12 mb-4" />
        <Typography variant="hero" className="text-center">
          Creating your clips...
        </Typography>
        <Typography variant="subtitle" className="text-center mt-2">
          {completed
            ? "Your clips are ready!"
            : "We're processing your video right now."}
        </Typography>
      </div>

      {/* Progress Card */}
      <Card className="w-full max-w-md text-center">
        {/* Circular progress */}
        <div className="flex justify-center mb-6">
          <ProgressIndicator
            progress={completed ? 100 : Math.round(progress)}
            size="xl"
            showPercentage={!completed}
          />
        </div>

        {/* Status text */}
        <Typography
          variant="title"
          className="mb-2"
          aria-live="polite"
          aria-atomic="true"
        >
          {completed
            ? "Complete!"
            : `${Math.round(progress)}%`}
        </Typography>

        {!completed && (
          <Typography variant="small" className="mb-6">
            Estimated time remaining: {eta}
          </Typography>
        )}

        {/* "What's Happening?" Timeline */}
        {!completed && (
          <div className="mb-6">
            <ProgressTimeline
              stages={PROCESSING_STAGES}
              currentProgress={progress}
            />
          </div>
        )}

        {/* Current Activity — rotating messages */}
        {!completed && (
          <div
            className="bg-slate-50 rounded-xl px-4 py-3 border border-slate-100"
            aria-live="polite"
            aria-atomic="true"
          >
            <div className="flex items-center justify-center gap-2">
              <AppIcon
                name="refresh"
                size="sm"
                className="text-emerald-500 motion-safe:animate-spin"
              />
              <span
                key={activityIndex}
                className="text-sm font-medium text-slate-700 transition-opacity duration-250 motion-safe:animate-in motion-safe:fade-in"
              >
                {ACTIVITY_MESSAGES[activityIndex]}
              </span>
            </div>
          </div>
        )}
      </Card>

      {/* Taking longer than expected — timeout warning */}
      {!completed && takingLonger && (
        <div className="mt-6 w-full max-w-md rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4">
          <div className="flex items-start gap-3">
            <AppIcon
              name="alertCircle"
              size="md"
              className="text-amber-500 shrink-0 mt-0.5"
            />
            <div>
              <p className="text-sm font-semibold text-amber-900">
                Taking longer than expected
              </p>
              <p className="text-sm text-amber-700 mt-1">
                Your video might be larger than usual. You can wait a bit
                longer or cancel and try again with a shorter video.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tips While You Wait */}
      {!completed && (
        <div className="mt-8 text-center max-w-sm">
          <Typography variant="caption" className="mb-2 block">
            <AppIcon
              name="info"
              size="sm"
              className="inline-block mr-1.5 text-slate-400 align-text-bottom"
            />
            Tip
          </Typography>
          <p
            key={tipIndex}
            className="text-sm text-slate-500 leading-relaxed transition-opacity duration-250 motion-safe:animate-in motion-safe:fade-in"
            aria-live="polite"
          >
            {TIPS[tipIndex]}
          </p>
        </div>
      )}

      {/* Success state actions */}
      {completed && (
        <div className="mt-8 flex flex-col items-center gap-4">
          <div className="flex items-center gap-2 text-emerald-600">
            <AppIcon name="checkCircle" size="lg" className="text-emerald-500" />
            <span className="text-sm font-medium">Redirecting to your clips...</span>
          </div>
          <Button
            variant="secondary"
            size="md"
            onClick={() => router.push("/app/clips" as never)}
          >
            View My Clips
          </Button>
        </div>
      )}

      {/* Cancel button */}
      {!completed && !cancelling && (
        <div className="mt-10">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowCancelDialog(true)}
          >
            Cancel Processing
          </Button>
        </div>
      )}

      {/* Cancelling state */}
      {cancelling && (
        <div className="mt-10 flex items-center gap-2 text-sm text-slate-400">
          <AppIcon name="refresh" size="sm" className="motion-safe:animate-spin" />
          Cancelling...
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmationDialog
        open={showCancelDialog}
        title="Cancel Processing?"
        message="Your progress will be lost. You'll need to start over from the beginning."
        confirmLabel="Yes, Cancel"
        cancelLabel="No, Keep Going"
        variant="danger"
        onConfirm={handleCancelConfirm}
        onCancel={() => setShowCancelDialog(false)}
      />
    </PageContainer>
  );
}
