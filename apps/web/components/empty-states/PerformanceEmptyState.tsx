"use client";

/**
 * Enhanced empty state for the Performance page.
 *
 * Shows an animated preview of what engagement stats will look like,
 * encouraging the user to complete a pipeline.
 */
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, Upload, Users } from "lucide-react";
import { Button } from "@/design-system/Button";

const previewMetrics = [
  { icon: TrendingUp, label: "View rate", value: "—" },
  { icon: Users, label: "Completion rate", value: "—" },
  { icon: BarChart3, label: "Engagement score", value: "—" },
];

export function PerformanceEmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex flex-col items-center justify-center h-[60vh] gap-8 px-6"
    >
      {/* Animated preview cards */}
      <div className="grid grid-cols-3 gap-3 max-w-md w-full">
        {previewMetrics.map((m, i) => (
          <motion.div
            key={m.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 + i * 0.12, duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
            className="rounded-xl border border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-1)] p-4 text-center"
          >
            <div className="flex justify-center mb-2">
              <m.icon className="h-5 w-5 text-[color:var(--color-text-tertiary)]" strokeWidth={1.5} />
            </div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)] mb-1">
              {m.label}
            </div>
            <div className="text-lg font-mono text-[color:var(--color-text-muted)]">{m.value}</div>
            {/* Skeleton shimmer */}
            <div className="mt-2 h-1.5 rounded-full bg-[color:var(--color-surface-2)] overflow-hidden">
              <motion.div
                className="h-full w-1/3 rounded-full bg-[color:var(--color-border-soft)]"
                animate={{ x: ["-100%", "300%"] }}
                transition={{ duration: 2.5, repeat: Infinity, ease: "linear" }}
              />
            </div>
          </motion.div>
        ))}
      </div>

      <div className="text-center max-w-sm space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">No engagement data yet</h2>
        <p className="text-sm text-[color:var(--color-text-secondary)] leading-relaxed">
          Complete a pipeline to see performance metrics — view rates, completion
          rates, and engagement scores for every exported clip. Data updates as
          feedback is collected from your publishing platforms.
        </p>
      </div>

      <a href="/app/upload">
        <Button variant="primary" size="lg">
          <Upload className="h-4 w-4" />
          Upload a match to get started
        </Button>
      </a>
    </motion.div>
  );
}
