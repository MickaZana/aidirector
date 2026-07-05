"use client";

/**
 * Enhanced empty state for the Clips page.
 *
 * Shows an explanatory illustration with a "Upload a match" CTA.
 * Used when there are no jobs yet.
 */
import { motion } from "framer-motion";
import { Clapperboard, Upload } from "lucide-react";
import { Button } from "@/design-system/Button";

export function ClipsEmptyState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="flex flex-col items-center justify-center h-[60vh] gap-6 px-6"
    >
      {/* Cinematic illustration */}
      <div className="relative">
        <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-[color:var(--color-accent-green)]/15 to-[color:var(--color-accent-blue)]/10 border border-[color:var(--color-border-accent)] flex items-center justify-center shadow-[0_0_80px_-20px_rgba(0,230,161,0.3)]">
          <Clapperboard className="h-10 w-10 text-[color:var(--color-accent-green)]" strokeWidth={1.5} />
        </div>
        {/* Decorative rings */}
        <div className="absolute -inset-4 rounded-3xl border border-[color:var(--color-border-soft)] opacity-30" />
        <div className="absolute -inset-8 rounded-[40px] border border-[color:var(--color-border-soft)] opacity-10" />
      </div>

      <div className="text-center max-w-sm space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">No clips yet</h2>
        <p className="text-sm text-[color:var(--color-text-secondary)] leading-relaxed">
          Upload a full match recording and the Director Agent will analyse every
          moment — surfacing goals, key passes, saves, and more as ranked clips.
        </p>
      </div>

      <a href="/app/upload">
        <Button variant="primary" size="lg">
          <Upload className="h-4 w-4" />
          Upload a match
        </Button>
      </a>

      <p className="text-[11px] text-[color:var(--color-text-tertiary)] font-mono uppercase tracking-wider">
        Supports mp4, mov, mkv · up to 2.2 GB
      </p>
    </motion.div>
  );
}
