"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BookOpen,
  Film,
  LayoutGrid,
  LineChart,
  Settings,
  Sparkles,
  Upload,
} from "lucide-react";
import { LogoMark } from "@/components/brand/LogoMark";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/app/upload", label: "Upload Studio", icon: Upload, accent: true },
  { href: "/app/jobs", label: "Pipelines", icon: Activity },
  { href: "/app/clips", label: "Clips Board", icon: LayoutGrid },
  { href: "/app/director", label: "Director Review", icon: Sparkles },
  { href: "/app/renders", label: "Render Center", icon: Film },
  { href: "/app/templates", label: "Brief Templates", icon: BookOpen },
  { href: "/app/performance", label: "Performance", icon: LineChart },
];

const NAV_BOTTOM = [
  { href: "/app/settings/billing", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden lg:flex flex-col w-64 shrink-0 border-r border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)]/60 backdrop-blur-sm h-screen sticky top-0">
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-[color:var(--color-border-soft)]">
        <LogoMark className="h-7 w-7" />
        <div className="flex flex-col">
          <span className="font-semibold tracking-tight text-sm">AI Director</span>
          <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
            Sports · v0.9
          </span>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map((item) => {
          const active = pathname?.startsWith(item.href) ?? false;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href as never}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium tracking-tight transition-colors duration-[var(--motion-fast)]",
                active
                  ? "bg-[color:var(--color-surface-2)] text-[color:var(--color-text-primary)] shadow-[inset_0_0_0_1px_var(--color-border-accent)]"
                  : "text-[color:var(--color-text-secondary)] hover:bg-[color:var(--color-surface-2)]/60 hover:text-[color:var(--color-text-primary)]",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  active
                    ? "text-[color:var(--color-accent-green)]"
                    : "text-[color:var(--color-text-tertiary)] group-hover:text-[color:var(--color-text-secondary)]",
                )}
                strokeWidth={2}
              />
              <span>{item.label}</span>
              {item.accent && !active && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[color:var(--color-accent-green)] shadow-[0_0_8px_rgba(0,230,161,0.7)]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom nav */}
      <nav className="px-3 py-2 border-t border-[color:var(--color-border-soft)]">
        {NAV_BOTTOM.map((item) => {
          const active = pathname?.startsWith(item.href) ?? false;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href as never}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium tracking-tight transition-colors duration-[var(--motion-fast)]",
                active
                  ? "bg-[color:var(--color-surface-2)] text-[color:var(--color-text-primary)] shadow-[inset_0_0_0_1px_var(--color-border-accent)]"
                  : "text-[color:var(--color-text-secondary)] hover:bg-[color:var(--color-surface-2)]/60 hover:text-[color:var(--color-text-primary)]",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 shrink-0 transition-colors",
                  active
                    ? "text-[color:var(--color-accent-green)]"
                    : "text-[color:var(--color-text-tertiary)] group-hover:text-[color:var(--color-text-secondary)]",
                )}
                strokeWidth={2}
              />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-[color:var(--color-border-soft)] text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
        OmegaClips · 78fcd57
      </div>
    </aside>
  );
}
