"use client";

import { Card } from "@/features/design-system";
import { VideoTypeSelector } from "./VideoTypeSelector";
import type { VideoType } from "../types";
import { PlatformSelector } from "./PlatformSelector";
import { ClipCountSelector } from "./ClipCountSelector";
import { PrimaryButton } from "./PrimaryButton";

interface QuickSetupProps {
  videoType: VideoType | null;
  onVideoTypeChange: (type: VideoType) => void;
  platforms: { id: string; label: string }[];
  onPlatformsChange: (ids: string[]) => void;
  clipCount: number;
  onClipCountChange: (count: number) => void;
  /** True when a file has been uploaded */
  canCreate: boolean;
  loading?: boolean;
  onCreateClips?: () => void;
}

/**
 * Quick Setup section — card container with all setup questions.
 * Uses design-system Card as the container.
 */
export function QuickSetup({
  videoType,
  onVideoTypeChange,
  platforms,
  onPlatformsChange,
  clipCount,
  onClipCountChange,
  canCreate,
  loading = false,
  onCreateClips,
}: QuickSetupProps) {
  return (
    <Card className="space-y-10">
      {/* Video type */}
      <VideoTypeSelector value={videoType} onChange={onVideoTypeChange} />

      {/* Divider */}
      <div className="border-t border-slate-100" />

      {/* Platforms */}
      <PlatformSelector
        platforms={platforms}
        selected={platforms.map((p) => p.id)}
        onChange={onPlatformsChange}
      />

      {/* Divider */}
      <div className="border-t border-slate-100" />

      {/* Clip count */}
      <ClipCountSelector
        value={clipCount}
        onChange={onClipCountChange}
        min={6}
        max={24}
      />

      {/* Divider */}
      <div className="border-t border-slate-100" />

      {/* CTA */}
      <PrimaryButton
        disabled={!canCreate}
        loading={loading}
        onClick={onCreateClips}
      >
        Create My Clips
      </PrimaryButton>
    </Card>
  );
}
