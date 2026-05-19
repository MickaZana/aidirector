"use client";

import { Bell, Search } from "lucide-react";
import { UserButton } from "@clerk/nextjs";
import { Badge } from "@/design-system/Badge";

interface TopBarProps {
  title: string;
  subtitle?: string;
  /** Right-side content (action buttons, badges, etc.) */
  trailing?: React.ReactNode;
}

export function TopBar({ title, subtitle, trailing }: TopBarProps) {
  return (
    <div className="sticky top-0 z-40 flex items-center justify-between gap-4 px-6 lg:px-8 h-16 border-b border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-0)]/85 backdrop-blur-xl">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3">
          <h1 className="text-base font-semibold tracking-tight truncate">{title}</h1>
          <Badge tone="muted">live</Badge>
        </div>
        {subtitle && (
          <p className="text-xs text-[color:var(--color-text-tertiary)] truncate">
            {subtitle}
          </p>
        )}
      </div>

      <div className="hidden md:flex items-center gap-2 rounded-full bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)] pl-3 pr-3 h-9 min-w-[260px] text-sm text-[color:var(--color-text-tertiary)]">
        <Search className="h-3.5 w-3.5" strokeWidth={2} />
        <span className="font-mono text-[11px] tracking-wider">⌘K</span>
        <span className="pl-1">Find a clip, job, export…</span>
      </div>

      <div className="flex items-center gap-3">
        {trailing}
        <button
          aria-label="Notifications"
          className="relative h-9 w-9 inline-flex items-center justify-center rounded-full border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)] hover:border-[color:var(--color-border-accent)] transition-colors"
        >
          <Bell className="h-4 w-4 text-[color:var(--color-text-secondary)]" strokeWidth={2} />
          <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-[color:var(--color-accent-green)] shadow-[0_0_8px_rgba(0,230,161,0.8)]" />
        </button>
        <UserButton
          appearance={{
            elements: {
              avatarBox: "h-9 w-9 ring-1 ring-[color:var(--color-border-soft)]",
            },
          }}
        />
      </div>
    </div>
  );
}
