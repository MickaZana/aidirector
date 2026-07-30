"use client";

import { useState } from "react";
import { cn } from "../utils/cn";
import { AppIcon } from "../components/AppIcon";
import type { AppIconName } from "../components/AppIcon";

type InfoBannerTone = "info" | "success" | "warning" | "error";

interface InfoBannerProps {
  tone?: InfoBannerTone;
  title?: string;
  message: string;
  /** Show a dismiss button */
  dismissable?: boolean;
  className?: string;
  /** Called after dismissal animation completes */
  onDismiss?: () => void;
}

const TONE_CONFIG: Record<
  InfoBannerTone,
  { icon: AppIconName; container: string; text: string; iconColor: string }
> = {
  info: {
    icon: "info",
    container: "bg-blue-50 border-blue-200",
    text: "text-blue-900",
    iconColor: "text-blue-500",
  },
  success: {
    icon: "checkCircle",
    container: "bg-emerald-50 border-emerald-200",
    text: "text-emerald-900",
    iconColor: "text-emerald-500",
  },
  warning: {
    icon: "alertCircle",
    container: "bg-amber-50 border-amber-200",
    text: "text-amber-900",
    iconColor: "text-amber-500",
  },
  error: {
    icon: "alertCircle",
    container: "bg-red-50 border-red-200",
    text: "text-red-900",
    iconColor: "text-red-500",
  },
};

/**
 * InfoBanner — A contextual banner for info, success, warning, or error messages.
 *
 * Usage:
 *   <InfoBanner tone="info" message="Processing may take a few minutes." />
 *   <InfoBanner tone="warning" title="Heads up" message="Long videos take longer." dismissable />
 *
 * Accessible: uses `role="status"` and `aria-live="polite"`.
 */
export function InfoBanner({
  tone = "info",
  title,
  message,
  dismissable = false,
  className,
  onDismiss,
}: InfoBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const config = TONE_CONFIG[tone];

  if (dismissed) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-start gap-3 rounded-2xl border p-4 transition-all duration-200",
        config.container,
        className,
      )}
    >
      <AppIcon
        name={config.icon}
        size="md"
        className={cn("shrink-0 mt-0.5", config.iconColor)}
      />
      <div className="flex-1 min-w-0">
        {title && (
          <p className="text-sm font-semibold mb-0.5 text-inherit">
            {title}
          </p>
        )}
        <p className={cn("text-sm", config.text)}>{message}</p>
      </div>
      {dismissable && onDismiss && (
        <button
          onClick={() => {
            setDismissed(true);
            onDismiss();
          }}
          className={cn(
            "shrink-0 rounded-lg p-1 transition-colors",
            config.text,
            "hover:bg-black/5",
          )}
          aria-label="Dismiss"
        >
          <AppIcon name="x" size="sm" />
        </button>
      )}
    </div>
  );
}
