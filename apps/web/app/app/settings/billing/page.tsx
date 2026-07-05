"use client";

import { useEffect, useState } from "react";
import { ExternalLink, Zap, Film, ArrowRight } from "lucide-react";
import { TopBar } from "@/components/layout/TopBar";
import { useApi } from "@/lib/api/runtime";

interface UsageData {
  plan: string;
  matches_used: number;
  matches_limit: number | null;
  exports_used: number;
  current_period_end: string | null;
}

interface SubscriptionData {
  plan: string;
  status: string;
  current_period_end: string | null;
}

const PLAN_LABELS: Record<string, string> = {
  starter: "Starter",
  pro: "Pro",
  studio: "Studio",
};

const PLAN_COLORS: Record<string, string> = {
  starter: "var(--color-text-secondary)",
  pro: "var(--color-accent-green)",
  studio: "var(--color-accent-blue)",
};

export default function BillingPage() {
  const { endpoints, mode } = useApi();
  const [usage, setUsage] = useState<UsageData | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (mode === "fixtures" || !endpoints) {
      setUsage({ plan: "starter", matches_used: 2, matches_limit: 5, exports_used: 6, current_period_end: null });
      setSubscription({ plan: "starter", status: "active", current_period_end: null });
      setLoading(false);
      return;
    }

    Promise.all([
      fetch("/api/billing/usage", { headers: endpoints ? {} : {} }).then((r) => r.json()),
      fetch("/api/billing/subscription").then((r) => r.json()),
    ])
      .then(([u, s]) => {
        setUsage(u);
        setSubscription(s);
      })
      .catch(() => {
        setUsage({ plan: "starter", matches_used: 0, matches_limit: 5, exports_used: 0, current_period_end: null });
        setSubscription({ plan: "starter", status: "active", current_period_end: null });
      })
      .finally(() => setLoading(false));
  }, [endpoints, mode]);

  async function openPortal() {
    setPortalLoading(true);
    try {
      const res = await fetch("/api/billing/portal");
      const { url } = await res.json();
      window.open(url, "_blank");
    } catch {
      alert("Could not open billing portal. Please try again.");
    } finally {
      setPortalLoading(false);
    }
  }

  const plan = subscription?.plan ?? "starter";
  const matchPct = usage?.matches_limit
    ? Math.min(100, Math.round(((usage.matches_used ?? 0) / usage.matches_limit) * 100))
    : 0;

  return (
    <>
      <TopBar title="Billing & Usage" subtitle="Manage your plan and track monthly usage" />
      <div className="px-6 lg:px-8 py-8 max-w-3xl space-y-6">

        {/* Current plan card */}
        <div
          className="rounded-xl p-6"
          style={{ background: "var(--color-surface-1)", border: "1px solid var(--color-border-soft)" }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[10px] uppercase tracking-widest mb-1" style={{ color: "var(--color-text-tertiary)" }}>
                Current plan
              </div>
              <div className="text-2xl font-bold" style={{ color: PLAN_COLORS[plan] ?? "var(--color-text-primary)" }}>
                {PLAN_LABELS[plan] ?? plan}
              </div>
              {subscription?.status && (
                <div className="text-xs mt-1" style={{ color: "var(--color-text-tertiary)" }}>
                  Status: <span style={{ color: subscription.status === "active" ? "var(--color-accent-green)" : "var(--color-accent-magenta)" }}>
                    {subscription.status}
                  </span>
                </div>
              )}
              {subscription?.current_period_end && (
                <div className="text-xs mt-0.5" style={{ color: "var(--color-text-tertiary)" }}>
                  Renews {new Date(subscription.current_period_end).toLocaleDateString()}
                </div>
              )}
            </div>
            <button
              onClick={openPortal}
              disabled={portalLoading}
              className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg transition-opacity disabled:opacity-50"
              style={{ background: "var(--color-surface-2)", border: "1px solid var(--color-border-strong)", color: "var(--color-text-primary)" }}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {portalLoading ? "Opening…" : "Manage billing"}
            </button>
          </div>
        </div>

        {/* Usage stats */}
        <div
          className="rounded-xl p-6 space-y-5"
          style={{ background: "var(--color-surface-1)", border: "1px solid var(--color-border-soft)" }}
        >
          <div className="text-sm font-semibold" style={{ color: "var(--color-text-primary)" }}>
            This month's usage
          </div>

          {loading ? (
            <div className="text-sm" style={{ color: "var(--color-text-tertiary)" }}>Loading…</div>
          ) : (
            <>
              {/* Matches */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                    <Zap className="h-3.5 w-3.5" style={{ color: "var(--color-accent-green)" }} />
                    Matches processed
                  </div>
                  <div className="text-sm font-semibold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
                    {usage?.matches_used ?? 0}
                    {usage?.matches_limit ? ` / ${usage.matches_limit}` : " / ∞"}
                  </div>
                </div>
                {usage?.matches_limit && (
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--color-surface-3)" }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${matchPct}%`,
                        background: matchPct >= 90
                          ? "var(--color-accent-magenta)"
                          : matchPct >= 70
                          ? "var(--color-accent-gold)"
                          : "var(--color-accent-green)",
                      }}
                    />
                  </div>
                )}
              </div>

              {/* Exports */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  <Film className="h-3.5 w-3.5" style={{ color: "var(--color-accent-blue)" }} />
                  Clips exported
                </div>
                <div className="text-sm font-semibold tabular-nums" style={{ color: "var(--color-text-primary)" }}>
                  {usage?.exports_used ?? 0}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Upgrade CTA for starter */}
        {plan === "starter" && (
          <div
            className="rounded-xl p-6 flex items-center justify-between gap-4"
            style={{
              background: "rgba(0,230,161,0.05)",
              border: "1px solid rgba(0,230,161,0.2)",
            }}
          >
            <div>
              <div className="text-sm font-semibold mb-1" style={{ color: "var(--color-text-primary)" }}>
                Upgrade to Pro
              </div>
              <div className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                50 matches/month · 1080p · no watermark · all platforms · $49/mo
              </div>
            </div>
            <button
              onClick={openPortal}
              className="flex items-center gap-2 text-sm font-semibold px-4 py-2 rounded-lg whitespace-nowrap"
              style={{
                background: "linear-gradient(135deg, var(--color-accent-green-dim), var(--color-accent-green))",
                color: "var(--color-surface-0)",
              }}
            >
              Upgrade <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

      </div>
    </>
  );
}
