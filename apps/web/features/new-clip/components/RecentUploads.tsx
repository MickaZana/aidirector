"use client";

import { AppIcon } from "@/features/design-system";
import { Card } from "@/features/design-system";
import type { RecentUpload } from "../types";

interface RecentUploadsProps {
  uploads: RecentUpload[];
}

/**
 * "Continue Working" card — shows the last 3 uploads so users can
 * quickly resume where they left off. Makes the app feel personal.
 * Uses design-system Card. Only renders when there are uploads to show.
 */
export function RecentUploads({ uploads }: RecentUploadsProps) {
  if (uploads.length === 0) return null;

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        <AppIcon name="clock" size="sm" className="text-slate-400" strokeWidth={2} />
        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">
          Continue Working
        </h2>
      </div>

      <div className="space-y-3">
        {uploads.slice(0, 3).map((upload) => (
          <button
            key={upload.id}
            type="button"
            className="flex w-full items-center justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50/50 px-4 py-3 transition-colors hover:bg-slate-100 hover:border-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 text-left"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xl shrink-0">{upload.emoji}</span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">
                  {upload.title}
                </p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {upload.subtitle}
                </p>
              </div>
            </div>
            <span className="flex items-center gap-1 text-xs font-medium text-emerald-600 shrink-0">
              Resume
              <AppIcon name="arrowRight" size="xs" strokeWidth={2} />
            </span>
          </button>
        ))}
      </div>
    </Card>
  );
}
