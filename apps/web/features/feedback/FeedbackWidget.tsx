"use client";

import { useState, useCallback, useEffect } from "react";
import { cn } from "@/features/design-system/utils/cn";
import { AppIcon } from "@/features/design-system";
import { analytics } from "@/services/analytics";

// ── Constants ────────────────────────────────────────────────

const STORAGE_KEY = "aidirector_feedback_submitted";
const RATING_LABELS = ["Not at all", "Somewhat", "Neutral", "Mostly", "Very"];

const QUESTIONS = [
  {
    id: "easy_to_use",
    label: "Was this easy to use?",
    type: "rating" as const,
  },
  {
    id: "useful_clips",
    label: "Did AI Director create useful clips?",
    type: "rating" as const,
  },
  {
    id: "confusion",
    label: "What confused you?",
    type: "text" as const,
    placeholder: "Nothing specific...",
  },
  {
    id: "improvements",
    label: "What would you improve?",
    type: "text" as const,
    placeholder: "Share your thoughts...",
  },
];

interface FeedbackAnswers {
  easy_to_use: number;
  useful_clips: number;
  confusion: string;
  improvements: string;
}

// ── Component ────────────────────────────────────────────────

/**
 * FeedbackWidget — lightweight in-app feedback collection.
 *
 * Appears as a floating button on the clips page after a project
 * is completed. Opens a modal with 4 frictionless questions.
 *
 * Submissions are stored in localStorage and can be flushed to
 * the backend later.
 */
export function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [answers, setAnswers] = useState<FeedbackAnswers>({
    easy_to_use: 0,
    useful_clips: 0,
    confusion: "",
    improvements: "",
  });
  const [dismissed, setDismissed] = useState(false);

  // Check if user has already submitted feedback
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "true") {
        setSubmitted(true);
      }
    } catch {
      // Storage unavailable
    }
  }, []);

  const handleRating = useCallback(
    (questionId: keyof FeedbackAnswers, value: number) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
    },
    [],
  );

  const handleText = useCallback(
    (questionId: keyof FeedbackAnswers, value: string) => {
      setAnswers((prev) => ({ ...prev, [questionId]: value }));
    },
    [],
  );

  const handleSubmit = useCallback(() => {
    setSubmitting(true);

    // Store submission
    try {
      localStorage.setItem(STORAGE_KEY, "true");
      localStorage.setItem(
        "aidirector_feedback_answers",
        JSON.stringify(answers),
      );
    } catch {
      // Storage unavailable
    }

    analytics.track("feedback_submitted", {
      easyToUse: answers.easy_to_use,
      usefulClips: answers.useful_clips,
      hasConfusion: answers.confusion.length > 0,
      hasImprovements: answers.improvements.length > 0,
    });

    // Simulate brief submission delay
    setTimeout(() => {
      setSubmitting(false);
      setSubmitted(true);
    }, 500);
  }, [answers]);

  const handleDismiss = useCallback(() => {
    setOpen(false);
    setDismissed(true);
  }, []);

  // Don't show if submitted or permanently dismissed this session
  if (submitted || dismissed) return null;

  return (
    <>
      {/* Floating trigger button */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-2 rounded-full bg-emerald-500 px-5 py-3 text-sm font-medium text-white shadow-lg hover:bg-emerald-600 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 duration-250"
          aria-label="Give feedback"
        >
          <AppIcon name="messageCircle" size="sm" />
          Give Feedback
        </button>
      )}

      {/* Modal overlay */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="feedback-title"
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={handleDismiss}
            aria-hidden="true"
          />

          {/* Modal */}
          <div
            className={cn(
              "relative z-10 w-full max-w-lg rounded-2xl bg-white border border-slate-200 shadow-xl p-6",
              "motion-safe:animate-in motion-safe:fade-in motion-safe:zoom-in-95 duration-200",
            )}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <h2
                id="feedback-title"
                className="text-lg font-semibold text-slate-900"
              >
                How&apos;s it going?
              </h2>
              <button
                type="button"
                onClick={handleDismiss}
                className="rounded-lg p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                aria-label="Close feedback"
              >
                <AppIcon name="x" size="sm" />
              </button>
            </div>

            {/* Questions */}
            <div className="space-y-6">
              {QUESTIONS.map((q) => (
                <div key={q.id}>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    {q.label}
                  </label>

                  {q.type === "rating" ? (
                    <div className="flex items-center gap-2">
                      {[1, 2, 3, 4, 5].map((value) => {
                        const id = q.id as keyof FeedbackAnswers;
                        const ratingValue = answers[id] as number;
                        const selected = ratingValue === value;
                        return (
                          <button
                            key={value}
                            type="button"
                            onClick={() => handleRating(id, value)}
                            className={cn(
                              "flex h-10 w-10 items-center justify-center rounded-lg border-2 text-sm font-medium transition-all",
                              selected
                                ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                                : "border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700",
                            )}
                            aria-label={`${value} — ${RATING_LABELS[value - 1]}`}
                          >
                            {value}
                          </button>
                        );
                      })}
                      <span className="ml-2 text-xs text-slate-400">
                        {(answers[q.id as keyof FeedbackAnswers] as number) > 0
                          ? RATING_LABELS[(answers[q.id as keyof FeedbackAnswers] as number) - 1]
                          : ""}
                      </span>
                    </div>
                  ) : (
                    <input
                      type="text"
                      value={answers[q.id as keyof FeedbackAnswers] as string}
                      onChange={(e) =>
                        handleText(q.id as keyof FeedbackAnswers, e.target.value)
                      }
                      placeholder={q.placeholder}
                      className="w-full rounded-xl border-2 border-slate-200 px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500/20"
                      aria-label={q.label}
                    />
                  )}
                </div>
              ))}
            </div>

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={handleDismiss}
                className="rounded-xl px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
              >
                Skip
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting}
                className="rounded-xl bg-emerald-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-600 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
              >
                {submitting ? "Sending..." : "Send Feedback"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
