"use client";

import { cn } from "../utils/cn";

interface PlatformBadgeProps {
  platform: string;
  className?: string;
}

/**
 * Platform badge mapping — human-readable labels for internal platform IDs.
 * Extend this as new platforms are added.
 */
const PLATFORM_LABELS: Record<string, string> = {
  youtube_shorts: "YouTube Shorts",
  tiktok: "TikTok",
  instagram_reels: "Instagram Reels",
  twitter: "X / Twitter",
  linkedin: "LinkedIn",
  facebook: "Facebook",
  snapchat: "Snapchat",
};

const PLATFORM_COLORS: Record<string, string> = {
  youtube_shorts: "bg-red-50 text-red-700 border-red-200",
  tiktok: "bg-blue-50 text-blue-700 border-blue-200",
  instagram_reels: "bg-purple-50 text-purple-700 border-purple-200",
  twitter: "bg-sky-50 text-sky-700 border-sky-200",
  linkedin: "bg-blue-50 text-blue-700 border-blue-200",
  facebook: "bg-indigo-50 text-indigo-700 border-indigo-200",
  snapchat: "bg-yellow-50 text-yellow-700 border-yellow-200",
};

/**
 * PlatformBadge — small pill badge for social platform labels.
 *
 * Usage:
 *   <PlatformBadge platform="youtube_shorts" />
 *   <PlatformBadge platform="tiktok" />
 *
 * Falls back to a neutral style for unknown platforms.
 */
export function PlatformBadge({ platform, className }: PlatformBadgeProps) {
  const label = PLATFORM_LABELS[platform] ?? platform;
  const color = PLATFORM_COLORS[platform] ?? "bg-slate-100 text-slate-600 border-slate-200";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium leading-tight",
        color,
        className,
      )}
    >
      {label}
    </span>
  );
}
