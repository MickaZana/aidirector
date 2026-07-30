"use client";

import * as LucideIcons from "lucide-react";
import { cn } from "../utils/cn";

/**
 * Icons available through AppIcon.
 * Add new names here as the project grows — one import per name, no bundle bloat.
 */
const ICON_MAP = {
  upload: LucideIcons.Upload,
  film: LucideIcons.Film,
  activity: LucideIcons.Activity,
  grid: LucideIcons.LayoutGrid,
  sparkles: LucideIcons.Sparkles,
  settings: LucideIcons.Settings,
  book: LucideIcons.BookOpen,
  chart: LucideIcons.LineChart,
  clock: LucideIcons.Clock,
  check: LucideIcons.Check,
  checkCircle: LucideIcons.CheckCircle,
  alertCircle: LucideIcons.AlertCircle,
  info: LucideIcons.Info,
  x: LucideIcons.X,
  arrowLeft: LucideIcons.ArrowLeft,
  download: LucideIcons.Download,
  trash: LucideIcons.Trash2,
  refresh: LucideIcons.RefreshCw,
  play: LucideIcons.Play,
  pause: LucideIcons.Pause,
  stop: LucideIcons.Square,   // Lucide uses Square for stop action
  file: LucideIcons.File,
  folder: LucideIcons.Folder,
  search: LucideIcons.Search,
  menu: LucideIcons.Menu,
  moreHorizontal: LucideIcons.MoreHorizontal,
  externalLink: LucideIcons.ExternalLink,
  link: LucideIcons.Link,
  // Media-type icons for the New Clip screen
  football: LucideIcons.Circle,      // fallback — football icon not in Lucide
  podcast: LucideIcons.Mic,
  basketball: LucideIcons.Circle,    // fallback — basketball icon not in Lucide
  // Icons used by New Clip components (added during Phase 2.4 UX hardening)
  zap: LucideIcons.Zap,
  brain: LucideIcons.Brain,
  chevronDown: LucideIcons.ChevronDown,
  cloudUpload: LucideIcons.CloudUpload,
  fileVideo: LucideIcons.FileVideo,
  minus: LucideIcons.Minus,
  plus: LucideIcons.Plus,
  arrowRight: LucideIcons.ArrowRight,
  messageCircle: LucideIcons.MessageCircle,
} as const;

export type AppIconName = keyof typeof ICON_MAP;

const SIZE_CLASSES = {
  xs: "h-3.5 w-3.5",
  sm: "h-4 w-4",
  md: "h-5 w-5",
  lg: "h-6 w-6",
  xl: "h-8 w-8",
  "2xl": "h-10 w-10",
  "3xl": "h-12 w-12",
} as const;

type AppIconSize = keyof typeof SIZE_CLASSES;

interface AppIconProps {
  /** Icon name from the ICON_MAP */
  name: AppIconName;
  /** Icon size */
  size?: AppIconSize;
  /** Optional className override */
  className?: string;
  /** Stroke width (Lucide default is 2) */
  strokeWidth?: number;
  /** Accessibility label */
  label?: string;
}

/**
 * AppIcon — single source of truth for all app icons.
 *
 * Usage:
 *   <AppIcon name="upload" size="lg" />
 *   <AppIcon name="checkCircle" size="md" className="text-emerald-500" />
 *
 * If you ever need to swap icon libraries, change only this file.
 * The entire app keeps working — zero refactors elsewhere.
 */
export function AppIcon({
  name,
  size = "md",
  className,
  strokeWidth = 2,
  label,
}: AppIconProps) {
  const IconComponent = ICON_MAP[name];

  if (!IconComponent) {
    // Fallback: render a placeholder so broken icons don't crash the app
    return (
      <span
        className={cn("inline-flex items-center justify-center", SIZE_CLASSES[size], className)}
        aria-label={label ?? `icon-${name}`}
        role="img"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-full w-full" aria-hidden="true">
          <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth={strokeWidth} />
          <circle cx="12" cy="11" r="2" stroke="currentColor" strokeWidth={strokeWidth} />
          <path d="M16 17a4 4 0 0 0-8 0" stroke="currentColor" strokeWidth={strokeWidth} />
        </svg>
      </span>
    );
  }

  return (
    <span
      className={cn("inline-flex items-center justify-center", className)}
      aria-label={label ?? `icon-${name}`}
      role="img"
    >
      <IconComponent
        className={SIZE_CLASSES[size]}
        strokeWidth={strokeWidth}
        aria-hidden="true"
      />
    </span>
  );
}
