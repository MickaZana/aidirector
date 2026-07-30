"use client";

import { AppIcon } from "@/features/design-system";
import { Card, Typography } from "@/features/design-system";

const STEPS = [
  {
    icon: "upload" as const,
    title: "Upload",
    description: "Upload your match or podcast.",
  },
  {
    icon: "brain" as const,
    title: "AI Analysis",
    description:
      "AI watches your video and finds the best moments automatically.",
  },
  {
    icon: "film" as const,
    title: "Clip Creation",
    description:
      "Professional clips are created with captions ready for social media.",
  },
  {
    icon: "download" as const,
    title: "Download",
    description: "Review, download or share your clips.",
  },
];

/**
 * How It Works section — four cards showing the workflow.
 * Uses design-system Card for each step. Cards stack on mobile, two columns on tablet.
 */
export function HowItWorks() {
  return (
    <section>
      <Typography variant="sectionTitle" className="text-center">
        How It Works
      </Typography>
      <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {STEPS.map((step) => (
          <Card key={step.title} dense className="text-center">
            <div className="mx-auto h-12 w-12 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center justify-center">
              <AppIcon name={step.icon} size="lg" className="text-emerald-500" strokeWidth={2} />
            </div>
            <p className="mt-4 text-lg font-semibold text-slate-900">
              {step.title}
            </p>
            <p className="mt-2 text-sm text-slate-500 leading-relaxed">
              {step.description}
            </p>
          </Card>
        ))}
      </div>
    </section>
  );
}
