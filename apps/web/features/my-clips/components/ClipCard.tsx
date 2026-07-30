"use client";

import { memo } from "react";
import { cn } from "@/features/design-system/utils/cn";
import {
  StatusBadge,
  PlatformBadge,
  Button,
  Card,
  AppIcon,
} from "@/features/design-system";
import type { Clip } from "../types";

interface ClipCardProps {
  clip: Clip;
  onPreview: (clip: Clip) => void;
  onDownload: (clip: Clip) => void;
  className?: string;
}

/**
 * ClipCard — a gallery card for a single generated clip.
 *
 * Shows thumbnail placeholder, title, duration, platform badges,
 * quality score, status, and action buttons (Preview / Download / More).
 *
 * Clicking the card body opens the preview panel.
 */
export const ClipCard = memo(function ClipCard({
  clip,
  onPreview,
  onDownload,
  className,
}: ClipCardProps) {
  return (
    <Card
      hoverable
      onClick={() => onPreview(clip)}
      className={cn("flex flex-col", className)}
    >
      {/* Thumbnail placeholder */}
      <div className="aspect-video rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 border border-slate-100 flex items-center justify-center mb-4 overflow-hidden">
        <div className="text-center">
          <AppIcon
            name="film"
            size="2xl"
            className="text-slate-300 mx-auto mb-1"
          />
          <span className="text-[11px] font-medium text-slate-400 block">
            {clip.duration}
          </span>
        </div>
      </div>

      {/* Title + score row */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-slate-900 leading-snug">
          {clip.title}
        </h3>
        <span className="shrink-0 flex items-center gap-1 text-xs font-semibold text-slate-700 bg-slate-100 rounded-md px-1.5 py-0.5">
          <span className="text-amber-500">&#9733;</span>
          {clip.score.toFixed(1)}
        </span>
      </div>

      {/* Platform badges */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {clip.platforms.map((p) => (
          <PlatformBadge key={p} platform={p} />
        ))}
      </div>

      {/* Status */}
      <div className="mb-4">
        <StatusBadge status={clip.status} />
      </div>

      {/* Actions */}
      <div className="mt-auto flex items-center gap-2">
        <Button
          size="sm"
          variant="primary"
          onClick={(e) => {
            e.stopPropagation();
            onPreview(clip);
          }}
          className="flex-1"
        >
          <AppIcon name="play" size="sm" />
          Preview
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={(e) => {
            e.stopPropagation();
            onDownload(clip);
          }}
          className="flex-1"
        >
          <AppIcon name="download" size="sm" />
          Download
        </Button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            // Future: open context menu
          }}
          className="rounded-lg p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          aria-label={`More options for ${clip.title}`}
        >
          <AppIcon name="moreHorizontal" size="md" />
        </button>
      </div>
    </Card>
  );
});
