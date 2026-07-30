"use client";

import { memo } from "react";
import { cn } from "@/features/design-system/utils/cn";
import {
  Button,
  StatusBadge,
  PlatformBadge,
  Badge,
  AppIcon,
  BottomSheet,
} from "@/features/design-system";
import type { Clip } from "../types";

interface PreviewPanelProps {
  clip: Clip | null;
  onClose: () => void;
  onDownload: (clip: Clip) => void;
}

/**
 * PreviewPanel — shows clip details in a side panel (desktop) or
 * bottom sheet (mobile). Rendered via BottomSheet.
 *
 * Displays:
 * - Large preview area
 * - Clip information (title, duration, score, platforms, status)
 * - Download, Share (placeholder), Copy Link (placeholder) buttons
 */
export const PreviewPanel = memo(function PreviewPanel({
  clip,
  onClose,
  onDownload,
}: PreviewPanelProps) {
  if (!clip) return null;

  return (
    <BottomSheet
      open={!!clip}
      onClose={onClose}
      title={clip.title}
    >
      {/* Large preview placeholder */}
      <div className="aspect-video rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 border border-slate-100 flex items-center justify-center mb-6">
        <div className="text-center">
          <AppIcon
            name="play"
            size="2xl"
            className="text-slate-300 mx-auto mb-2"
          />
          <span className="text-xs font-medium text-slate-400">
            {clip.duration}
          </span>
        </div>
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Duration
          </span>
          <p className="text-sm font-semibold text-slate-900 mt-0.5">
            {clip.duration}
          </p>
        </div>
        <div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Quality Score
          </span>
          <p className="text-sm font-semibold text-slate-900 mt-0.5 flex items-center gap-1">
            <span className="text-amber-500">&#9733;</span>
            {clip.score.toFixed(1)}
          </p>
        </div>
        <div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Status
          </span>
          <div className="mt-1">
            <StatusBadge status={clip.status} />
          </div>
        </div>
        <div>
          <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
            Created
          </span>
          <p className="text-sm text-slate-900 mt-0.5">
            {clip.createdAt}
          </p>
        </div>
      </div>

      {/* Platforms */}
      <div className="mb-6">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider block mb-2">
          Platforms
        </span>
        <div className="flex flex-wrap gap-1.5">
          {clip.platforms.map((p) => (
            <PlatformBadge key={p} platform={p} />
          ))}
        </div>
      </div>

      {/* Description / filename */}
      <div className="mb-6 p-3 rounded-xl bg-slate-50 border border-slate-100">
        <p className="text-xs text-slate-500 leading-relaxed">
          AI-generated clip from your video. Optimised for vertical viewing
          on social platforms.
        </p>
      </div>

      {/* Action buttons */}
      <div className="space-y-3">
        <Button
          size="lg"
          variant="primary"
          className="w-full"
          onClick={() => onDownload(clip)}
        >
          <AppIcon name="download" size="md" />
          Download Clip
        </Button>
        <div className="grid grid-cols-2 gap-3">
          <Button
            size="md"
            variant="secondary"
            className="w-full"
            onClick={() => {
              // Placeholder: wire up sharing
            }}
          >
            <AppIcon name="externalLink" size="sm" />
            Share
          </Button>
          <Button
            size="md"
            variant="secondary"
            className="w-full"
            onClick={() => {
              // Placeholder: copy link
            }}
          >
            <AppIcon name="link" size="sm" />
            Copy Link
          </Button>
        </div>
      </div>
    </BottomSheet>
  );
});
