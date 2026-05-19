/**
 * Render state machine — per render-job, not per upload.
 *
 * Mirrors `apps/api/src/api/models/pipeline.py::RenderJobStatus`
 * exactly so a server-side row can hydrate a snapshot directly.
 */

export type RenderState =
  | "queued"
  | "preparing"
  | "rendering"
  | "exporting"
  | "uploaded"
  | "failed";

export type RenderEvent =
  | { type: "ENQUEUED" }
  | { type: "PREPARE_STARTED" }
  | { type: "RENDER_STARTED" }
  | { type: "EXPORT_STARTED" }
  | { type: "UPLOAD_SUCCEEDED" }
  | { type: "RENDER_FAILED"; error: string }
  | { type: "RESET" };

export interface RenderContext {
  /** Wall-clock progress over the FFmpeg subprocess if we have it. */
  bytesWritten: number | null;
  durationSeconds: number | null;
  error: string | null;
}

export interface RenderSnapshot {
  state: RenderState;
  context: RenderContext;
}

export const INITIAL_RENDER_SNAPSHOT: RenderSnapshot = {
  state: "queued",
  context: { bytesWritten: null, durationSeconds: null, error: null },
};

const TRANSITIONS: Partial<Record<RenderState, RenderEvent["type"][]>> = {
  queued: ["PREPARE_STARTED", "RENDER_FAILED", "RESET"],
  preparing: ["RENDER_STARTED", "RENDER_FAILED", "RESET"],
  rendering: ["EXPORT_STARTED", "RENDER_FAILED", "RESET"],
  exporting: ["UPLOAD_SUCCEEDED", "RENDER_FAILED", "RESET"],
  uploaded: ["RESET"],
  failed: ["RESET"],
};

export function reduceRender(
  snap: RenderSnapshot,
  event: RenderEvent,
): RenderSnapshot {
  const allowed = TRANSITIONS[snap.state] ?? [];
  if (!allowed.includes(event.type)) return snap;

  switch (event.type) {
    case "ENQUEUED":
      return INITIAL_RENDER_SNAPSHOT;
    case "PREPARE_STARTED":
      return { state: "preparing", context: snap.context };
    case "RENDER_STARTED":
      return { state: "rendering", context: snap.context };
    case "EXPORT_STARTED":
      return { state: "exporting", context: snap.context };
    case "UPLOAD_SUCCEEDED":
      return { state: "uploaded", context: snap.context };
    case "RENDER_FAILED":
      return { state: "failed", context: { ...snap.context, error: event.error } };
    case "RESET":
      return INITIAL_RENDER_SNAPSHOT;
  }
}

export const RENDER_STATE_LABELS: Record<RenderState, string> = {
  queued: "Queued",
  preparing: "Preparing",
  rendering: "Rendering",
  exporting: "Exporting",
  uploaded: "Uploaded",
  failed: "Failed",
};
