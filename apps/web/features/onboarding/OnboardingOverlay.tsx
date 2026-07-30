"use client";

import { useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/features/design-system/utils/cn";
import { AppIcon, Typography } from "@/features/design-system";
import type { AppIconName } from "@/features/design-system";

// ── Constants ────────────────────────────────────────────────

const STORAGE_KEY = "aidirector_onboarding_dismissed";

const STEPS = [
  {
    icon: "upload" as AppIconName,
    title: "Upload a video",
    description:
      "Drop your match footage or podcast recording. We accept MP4, MOV, and MKV files up to 2.2 GB.",
  },
  {
    icon: "brain" as AppIconName,
    title: "AI creates clips",
    description:
      "Our AI watches your video, finds the best moments, and generates short-form clips optimised for social platforms.",
  },
  {
    icon: "download" as AppIconName,
    title: "Review and download",
    description:
      "Browse your clips, preview them, and download the ones you love. Each clip is formatted for YouTube Shorts, TikTok, and Instagram Reels.",
  },
];

// ── Component ────────────────────────────────────────────────

/**
 * OnboardingOverlay — first-run experience shown on first visit.
 *
 * Three steps introducing the core workflow:
 * 1. Upload a video
 * 2. AI creates clips
 * 3. Review and download
 *
 * Dismissed permanently via localStorage. Can be reset by clearing
 * browser storage or calling `resetOnboarding()`.
 */
export function OnboardingOverlay() {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored !== "true") {
        // First visit — show onboarding after a brief delay
        const timer = setTimeout(() => setVisible(true), 600);
        setDismissed(false);
        return () => clearTimeout(timer);
      }
    } catch {
      // Storage unavailable — skip onboarding
    }
  }, []);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    setDismissed(true);
    try {
      localStorage.setItem(STORAGE_KEY, "true");
    } catch {
      // Storage unavailable
    }
  }, []);

  const handleNext = useCallback(() => {
    if (step < STEPS.length - 1) {
      setStep((s) => s + 1);
    } else {
      handleDismiss();
    }
  }, [step, handleDismiss]);

  const handlePrev = useCallback(() => {
    if (step > 0) {
      setStep((s) => s - 1);
    }
  }, []);

  if (dismissed || !visible) return null;

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleDismiss}
        aria-hidden="true"
      />

      {/* Card */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }}
        className={cn(
          "relative z-10 w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-xl p-8 text-center",
        )}
      >
        {/* Step indicator dots */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={cn(
                "h-2 rounded-full transition-all duration-250",
                i === step
                  ? "w-8 bg-emerald-500"
                  : "w-2 bg-slate-200",
              )}
            />
          ))}
        </div>

        {/* Step icon */}
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col items-center"
          >
            <div className="mx-auto h-16 w-16 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center justify-center mb-5">
              <AppIcon
                name={current.icon}
                size="2xl"
                className="text-emerald-500"
                strokeWidth={1.5}
              />
            </div>

            <Typography
              id="onboarding-title"
              variant="title"
              className="text-slate-900 mb-2"
            >
              {current.title}
            </Typography>

            <Typography
              variant="small"
              className="text-slate-500 max-w-xs mx-auto"
            >
              {current.description}
            </Typography>
          </motion.div>
        </AnimatePresence>

        {/* Actions */}
        <div className="mt-8 flex items-center justify-between">
          <button
            type="button"
            onClick={handlePrev}
            disabled={step === 0}
            className={cn(
              "rounded-xl px-4 py-2.5 text-sm font-medium transition-colors",
              step === 0
                ? "text-slate-300 cursor-not-allowed"
                : "text-slate-600 hover:bg-slate-100",
            )}
            aria-label="Previous step"
          >
            Back
          </button>

          <button
            type="button"
            onClick={handleNext}
            className="rounded-xl bg-emerald-500 px-6 py-2.5 text-sm font-medium text-white hover:bg-emerald-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
          >
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>

        {/* Skip link */}
        <button
          type="button"
          onClick={handleDismiss}
          className="mt-4 text-xs text-slate-400 hover:text-slate-600 transition-colors underline underline-offset-2"
        >
          Skip tutorial
        </button>
      </motion.div>
    </div>
  );
}

/**
 * Reset onboarding so it shows again on next visit.
 * Useful for testing or if the user wants to retake the tour.
 */
export function resetOnboarding(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage unavailable
  }
}
