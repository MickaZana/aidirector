"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CreditCard, Shield } from "lucide-react";
import { cn } from "@/lib/cn";

const SETTINGS_TABS = [
  { href: "/app/settings/billing", label: "Billing & Usage", icon: CreditCard },
  { href: "/app/settings/dsr", label: "Data & Privacy", icon: Shield },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen">
      {/* Sub-navigation */}
      <div className="sticky top-16 z-30 flex items-center gap-1 px-6 lg:px-8 h-12 border-b border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-0)]/70 backdrop-blur-xl">
        {SETTINGS_TABS.map((tab) => {
          const active = pathname === tab.href;
          const Icon = tab.icon;
          return (
            <Link
              key={tab.href}
              href={tab.href as never}
              className={cn(
                "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium tracking-tight transition-colors duration-[var(--motion-fast)]",
                active
                  ? "bg-[color:var(--color-surface-2)] text-[color:var(--color-text-primary)] shadow-[inset_0_0_0_1px_var(--color-border-accent)]"
                  : "text-[color:var(--color-text-secondary)] hover:text-[color:var(--color-text-primary)] hover:bg-[color:var(--color-surface-2)]/60",
              )}
            >
              <Icon className="h-4 w-4" strokeWidth={2} />
              {tab.label}
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}
