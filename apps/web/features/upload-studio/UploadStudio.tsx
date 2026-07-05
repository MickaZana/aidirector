"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Cloud, FileVideo, Sparkles, Trash2, Zap } from "lucide-react";
import { Surface } from "@/design-system/Surface";
import { Badge } from "@/design-system/Badge";
import { Button } from "@/design-system/Button";
import { ProgressTrack } from "@/design-system/ProgressTrack";
import { cn } from "@/lib/cn";
import { formatBytes, formatRelativeTime } from "@/lib/format";
import {
  UPLOAD_STATE_LABELS,
  type UploadState,
} from "@/services/state-machines/upload-machine";
import { useUploadQueue, type QueueEntry } from "@/stores/upload-queue";
import { processUpload } from "@/services/upload-service";
import { useApi } from "@/lib/api/runtime";

const SPORTS = [
  { id: "football", label: "Football", emoji: "⚽" },
  { id: "basketball", label: "Basketball", emoji: "🏀", disabled: true },
  { id: "rugby", label: "Rugby", emoji: "🏉", disabled: true },
  { id: "f1", label: "F1", emoji: "🏎", disabled: true },
];

const PLATFORMS = [
  { id: "youtube_shorts", label: "YouTube Shorts", aspect: "9:16" },
  { id: "tiktok", label: "TikTok", aspect: "9:16" },
  { id: "instagram_reels", label: "Instagram Reels", aspect: "9:16" },
  { id: "x", label: "X", aspect: "16:9" },
];

export function UploadStudio() {
  const { endpoints, mode } = useApi();
  const enqueue = useUploadQueue((s) => s.enqueue);
  const entries = useUploadQueue((s) => s.entries);
  const dispatch = useUploadQueue((s) => s.dispatch);
  const clearCompleted = useUploadQueue((s) => s.clearCompleted);
  const inputRef = useRef<HTMLInputElement>(null);

  const [sport, setSport] = useState<string>("football");
  const [platforms, setPlatforms] = useState<string[]>([
    "youtube_shorts",
    "tiktok",
    "instagram_reels",
  ]);
  const [dragging, setDragging] = useState(false);

  const togglePlatform = (id: string) =>
    setPlatforms((cur) => (cur.includes(id) ? cur.filter((p) => p !== id) : [...cur, id]));

  const onFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      Array.from(files).forEach((file) =>
        enqueue({
          fileName: file.name,
          fileSize: file.size,
          file,
          sport,
          platformTargets: platforms,
        }),
      );
    },
    [enqueue, sport, platforms],
  );

  // ── Auto-process idle entries ───────────────────────────────────────
  const processingRef = useRef(false);
  useEffect(() => {
    if (!endpoints || mode !== "live") return;
    if (processingRef.current) return;

    const idleEntry = entries.find(
      (e) => e.snapshot.state === "idle" && e.file,
    );
    if (!idleEntry) return;

    processingRef.current = true;

    // Transition idle → selecting, then start the pipeline
    dispatch(idleEntry.id, {
      type: "FILE_SELECTED",
      file: idleEntry.file!,
    });

    processUpload(
      endpoints,
      idleEntry.id,
      idleEntry.file!,
      idleEntry.sport,
      dispatch,
    ).finally(() => {
      processingRef.current = false;
    });
  }, [endpoints, mode, entries, dispatch]);

  return (
    <div className="px-6 lg:px-8 py-8 space-y-8">
      <header className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Upload Studio</h1>
          <p className="text-sm text-[color:var(--color-text-secondary)] mt-1.5 max-w-2xl">
            Drop a match. The Director Agent decides what becomes a clip, how it's framed,
            and which renderer produces it — captioned, auto-cropped, platform-ready in minutes.
          </p>
        </div>
        <Badge status="stable" pulse>
          OmegaClips 78fcd57 · ready
        </Badge>
      </header>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Drop zone */}
        <Surface variant="elevated" className="lg:col-span-2 relative overflow-hidden">
          <input
            ref={inputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska"
            multiple
            className="hidden"
            onChange={(e) => onFiles(e.target.files)}
          />
          <motion.div
            initial={false}
            animate={dragging ? { scale: 1.02 } : { scale: 1 }}
            transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              onFiles(e.dataTransfer?.files ?? null);
            }}
            onClick={() => inputRef.current?.click()}
            className={cn(
              "cursor-pointer rounded-xl border-2 border-dashed p-12 flex flex-col items-center justify-center text-center transition-colors min-h-[260px]",
              dragging
                ? "border-[color:var(--color-accent-green)] bg-[color:var(--color-accent-green)]/5"
                : "border-[color:var(--color-border-soft)] hover:border-[color:var(--color-border-accent)] bg-[color:var(--color-surface-1)]/60",
            )}
          >
            <div className="relative h-16 w-16 rounded-2xl bg-gradient-to-br from-[color:var(--color-accent-green)]/20 to-[color:var(--color-accent-blue)]/20 border border-[color:var(--color-border-accent)] flex items-center justify-center shadow-[0_0_60px_-12px_rgba(0,230,161,0.4)]">
              <Cloud className="h-7 w-7 text-[color:var(--color-accent-green)]" strokeWidth={2} />
            </div>
            <h2 className="mt-5 text-xl font-semibold tracking-tight">
              Drop full match here
            </h2>
            <p className="mt-1.5 text-sm text-[color:var(--color-text-secondary)] max-w-md">
              Up to 2.2 GB · mp4, mov, mkv · raw broadcast or recorded stream
            </p>
            <div className="mt-6 flex items-center gap-3">
              <Button variant="primary">
                <FileVideo className="h-4 w-4" />
                Choose file
              </Button>
              <span className="text-[11px] text-[color:var(--color-text-tertiary)] font-mono uppercase tracking-wider">
                or paste a URL
              </span>
            </div>
          </motion.div>

          {/* Pipeline preview */}
          <div className="mt-8 rounded-xl bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] p-4">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="h-3.5 w-3.5 text-[color:var(--color-accent-gold)]" />
              <span className="text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
                Pipeline preview
              </span>
            </div>
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              {[
                "Analysis · FI-1→FI-13",
                "Ranking · window_ranking",
                "Director Plan · deterministic",
                "Render · FFmpeg",
                "Export · canonical identity",
                "Feedback · trust gradient",
              ].map((label, i) => (
                <div key={label} className="flex items-center gap-2 shrink-0">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-secondary)] px-2 py-1 rounded-md bg-[color:var(--color-surface-1)] border border-[color:var(--color-border-soft)]">
                    {label}
                  </span>
                  {i < 5 && (
                    <span className="text-[color:var(--color-text-muted)] text-xs">→</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Surface>

        {/* Sport + platforms */}
        <Surface variant="card" className="space-y-6">
          <div>
            <h3 className="text-sm font-semibold tracking-tight">Sport</h3>
            <p className="text-xs text-[color:var(--color-text-tertiary)] mt-0.5">
              Drives which intelligence layer activates.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              {SPORTS.map((s) => (
                <button
                  key={s.id}
                  disabled={s.disabled}
                  onClick={() => setSport(s.id)}
                  className={cn(
                    "rounded-lg border px-3 py-3 text-left transition-colors",
                    s.id === sport
                      ? "border-[color:var(--color-accent-green)]/50 bg-[color:var(--color-accent-green)]/10"
                      : "border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-2)]",
                    s.disabled && "opacity-40 cursor-not-allowed",
                    !s.disabled && s.id !== sport && "hover:border-[color:var(--color-border-strong)]",
                  )}
                >
                  <div className="text-lg">{s.emoji}</div>
                  <div className="mt-1 text-sm font-medium">{s.label}</div>
                  {s.disabled && (
                    <div className="text-[10px] uppercase tracking-wider text-[color:var(--color-text-muted)] mt-0.5">
                      soon
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold tracking-tight">Platform targets</h3>
            <p className="text-xs text-[color:var(--color-text-tertiary)] mt-0.5">
              Director Plan emits one variant per target.
            </p>
            <div className="mt-3 space-y-1.5">
              {PLATFORMS.map((p) => {
                const active = platforms.includes(p.id);
                return (
                  <button
                    key={p.id}
                    onClick={() => togglePlatform(p.id)}
                    className={cn(
                      "w-full flex items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors",
                      active
                        ? "border-[color:var(--color-accent-green)]/40 bg-[color:var(--color-accent-green)]/8"
                        : "border-[color:var(--color-border-soft)] bg-[color:var(--color-surface-2)] hover:border-[color:var(--color-border-strong)]",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          "h-2 w-2 rounded-full",
                          active
                            ? "bg-[color:var(--color-accent-green)] shadow-[0_0_8px_rgba(0,230,161,0.8)]"
                            : "bg-[color:var(--color-border-strong)]",
                        )}
                      />
                      <span className="text-sm font-medium">{p.label}</span>
                    </div>
                    <span className="font-mono text-[10px] uppercase tracking-wider text-[color:var(--color-text-tertiary)]">
                      {p.aspect}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-lg bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] p-3">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-[color:var(--color-text-tertiary)]">
              <Zap className="h-3 w-3" /> Cost estimate
            </div>
            <div className="mt-1 font-mono text-2xl tabular-nums">
              ~$0.{platforms.length * 6}
            </div>
            <div className="text-xs text-[color:var(--color-text-tertiary)]">
              per match · {platforms.length} variants × ~$0.06
            </div>
          </div>
        </Surface>
      </div>

      {/* Active queue */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold tracking-tight uppercase tracking-[0.18em] text-[color:var(--color-text-secondary)]">
            Active queue
            <span className="ml-2 font-mono text-[color:var(--color-text-tertiary)]">
              {entries.length}
            </span>
          </h2>
          {entries.some((e) => e.snapshot.state === "complete" || e.snapshot.state === "failed") && (
            <Button variant="ghost" size="sm" onClick={clearCompleted}>
              <Trash2 className="h-3.5 w-3.5" /> Clear completed
            </Button>
          )}
        </div>
        {entries.length === 0 ? (
          <Surface variant="card" className="text-center py-12 text-sm text-[color:var(--color-text-tertiary)]">
            No active uploads. Drop a file above to start.
          </Surface>
        ) : (
          <div className="grid gap-3">
            {entries.map((e) => (
              <QueueRow key={e.id} entry={e} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function QueueRow({ entry }: { entry: QueueEntry }) {
  const { snapshot } = entry;
  const dispatch = useUploadQueue((s) => s.dispatch);
  const remove = useUploadQueue((s) => s.remove);
  const progress = snapshot.context.file && snapshot.state === "uploading"
    ? snapshot.context.bytesUploaded / Math.max(1, entry.fileSize)
    : snapshot.state === "complete"
      ? 1
      : statePseudoProgress(snapshot.state);

  return (
    <Surface variant="card" dense className="flex items-center gap-4">
      <div className="h-12 w-12 rounded-lg bg-[color:var(--color-surface-2)] border border-[color:var(--color-border-soft)] flex items-center justify-center">
        <FileVideo className="h-4 w-4 text-[color:var(--color-text-secondary)]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium truncate">{entry.fileName}</span>
          <Badge status={stateToStatusKey(snapshot.state)} pulse={isInflight(snapshot.state)}>
            {UPLOAD_STATE_LABELS[snapshot.state]}
          </Badge>
        </div>
        <div className="mt-1 text-[11px] text-[color:var(--color-text-tertiary)] flex items-center gap-3 flex-wrap font-mono uppercase tracking-wider">
          <span>{formatBytes(entry.fileSize)}</span>
          <span>{entry.sport}</span>
          <span>{entry.platformTargets.length} platforms</span>
          <span>{formatRelativeTime(entry.createdAt)}</span>
        </div>
        <div className="mt-2 max-w-md">
          <ProgressTrack value={progress} tone={isInflight(snapshot.state) ? "blue" : "accent"} />
        </div>
        {/* Error detail + retry for failed uploads */}
        {snapshot.state === "failed" && (
          <div className="mt-3 flex items-center gap-3">
            {snapshot.context.error && (
              <span className="text-[11px] text-[color:var(--color-status-failed)] font-mono">
                {snapshot.context.error.message}
              </span>
            )}
            <button
              onClick={() => { remove(entry.id); }}
              className="text-[11px] font-semibold text-[color:var(--color-text-tertiary)] hover:text-[color:var(--color-text-primary)] transition-colors"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>
    </Surface>
  );
}

function statePseudoProgress(s: UploadState): number {
  const order: UploadState[] = [
    "selecting", "presigning", "uploading", "uploaded",
    "analyzing", "ranking", "directing", "rendering",
    "exporting", "complete",
  ];
  const idx = order.indexOf(s);
  if (idx < 0) return 0;
  return idx / (order.length - 1);
}

function isInflight(s: UploadState): boolean {
  return ["presigning", "uploading", "analyzing", "ranking", "directing", "rendering", "exporting"].includes(s);
}

function stateToStatusKey(s: UploadState): "queued" | "running" | "succeeded" | "failed" {
  if (s === "complete") return "succeeded";
  if (s === "failed") return "failed";
  if (isInflight(s)) return "running";
  return "queued";
}
