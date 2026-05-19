/**
 * Upload state machine.
 *
 * Strictly typed transitions for the upload → analyze → rank → direct
 * → render → export → feedback pipeline. The state machine is owned by
 * `services/upload-service.ts`; components subscribe to derived state
 * via hooks and never call transitions directly.
 *
 * No async work happens here. This module is a pure reducer.
 */

export type UploadState =
  | "idle"
  | "selecting"
  | "presigning"
  | "uploading"
  | "uploaded"
  | "analyzing"
  | "ranking"
  | "directing"
  | "rendering"
  | "exporting"
  | "complete"
  | "failed";

export type UploadEvent =
  | { type: "FILE_SELECTED"; file: File }
  | { type: "PRESIGN_REQUESTED" }
  | { type: "PRESIGN_OK"; uploadId: string; presignedUrl: string }
  | { type: "PRESIGN_FAILED"; error: string }
  | { type: "UPLOAD_PROGRESS"; bytesUploaded: number }
  | { type: "UPLOAD_OK" }
  | { type: "UPLOAD_FAILED"; error: string }
  | { type: "ANALYSIS_STARTED" }
  | { type: "RANKING_STARTED" }
  | { type: "DIRECTING_STARTED" }
  | { type: "RENDERING_STARTED" }
  | { type: "EXPORTING_STARTED" }
  | { type: "PIPELINE_COMPLETED" }
  | { type: "PIPELINE_FAILED"; error: string; stage: UploadState }
  | { type: "RESET" };

export interface UploadContext {
  uploadId: string | null;
  file: File | null;
  bytesUploaded: number;
  presignedUrl: string | null;
  error: { message: string; stage: UploadState } | null;
}

export interface UploadSnapshot {
  state: UploadState;
  context: UploadContext;
}

export const INITIAL_UPLOAD_SNAPSHOT: UploadSnapshot = {
  state: "idle",
  context: {
    uploadId: null,
    file: null,
    bytesUploaded: 0,
    presignedUrl: null,
    error: null,
  },
};

/**
 * Allowed transitions. Anything not listed throws.
 *
 * Components can render *every* state — the visual progression follows
 * the order: selecting → presigning → uploading → uploaded → analyzing
 * → ranking → directing → rendering → exporting → complete.
 */
const TRANSITIONS: Partial<Record<UploadState, UploadEvent["type"][]>> = {
  idle: ["FILE_SELECTED", "RESET"],
  selecting: ["PRESIGN_REQUESTED", "RESET"],
  presigning: ["PRESIGN_OK", "PRESIGN_FAILED", "RESET"],
  uploading: ["UPLOAD_PROGRESS", "UPLOAD_OK", "UPLOAD_FAILED", "RESET"],
  uploaded: ["ANALYSIS_STARTED", "PIPELINE_FAILED", "RESET"],
  analyzing: ["RANKING_STARTED", "PIPELINE_FAILED", "RESET"],
  ranking: ["DIRECTING_STARTED", "PIPELINE_FAILED", "RESET"],
  directing: ["RENDERING_STARTED", "PIPELINE_FAILED", "RESET"],
  rendering: ["EXPORTING_STARTED", "PIPELINE_FAILED", "RESET"],
  exporting: ["PIPELINE_COMPLETED", "PIPELINE_FAILED", "RESET"],
  complete: ["RESET"],
  failed: ["RESET"],
};

export function reduceUpload(
  snap: UploadSnapshot,
  event: UploadEvent,
): UploadSnapshot {
  const allowed = TRANSITIONS[snap.state] ?? [];
  if (!allowed.includes(event.type)) {
    // Silent on unknown transitions — UI doesn't care, the service drops
    // late events from cancelled flows.
    return snap;
  }

  switch (event.type) {
    case "FILE_SELECTED":
      return { state: "selecting", context: { ...snap.context, file: event.file, error: null } };
    case "PRESIGN_REQUESTED":
      return { state: "presigning", context: snap.context };
    case "PRESIGN_OK":
      return {
        state: "uploading",
        context: {
          ...snap.context,
          uploadId: event.uploadId,
          presignedUrl: event.presignedUrl,
          bytesUploaded: 0,
        },
      };
    case "PRESIGN_FAILED":
      return {
        state: "failed",
        context: {
          ...snap.context,
          error: { message: event.error, stage: "presigning" },
        },
      };
    case "UPLOAD_PROGRESS":
      return {
        state: "uploading",
        context: { ...snap.context, bytesUploaded: event.bytesUploaded },
      };
    case "UPLOAD_OK":
      return { state: "uploaded", context: snap.context };
    case "UPLOAD_FAILED":
      return {
        state: "failed",
        context: { ...snap.context, error: { message: event.error, stage: "uploading" } },
      };
    case "ANALYSIS_STARTED":
      return { state: "analyzing", context: snap.context };
    case "RANKING_STARTED":
      return { state: "ranking", context: snap.context };
    case "DIRECTING_STARTED":
      return { state: "directing", context: snap.context };
    case "RENDERING_STARTED":
      return { state: "rendering", context: snap.context };
    case "EXPORTING_STARTED":
      return { state: "exporting", context: snap.context };
    case "PIPELINE_COMPLETED":
      return { state: "complete", context: snap.context };
    case "PIPELINE_FAILED":
      return {
        state: "failed",
        context: {
          ...snap.context,
          error: { message: event.error, stage: event.stage },
        },
      };
    case "RESET":
      return INITIAL_UPLOAD_SNAPSHOT;
  }
}

/** Convenience: human-readable label for a state. */
export const UPLOAD_STATE_LABELS: Record<UploadState, string> = {
  idle: "Idle",
  selecting: "Selecting file",
  presigning: "Preparing upload",
  uploading: "Uploading",
  uploaded: "Uploaded",
  analyzing: "Analyzing",
  ranking: "Ranking moments",
  directing: "Directing edits",
  rendering: "Rendering variants",
  exporting: "Exporting",
  complete: "Complete",
  failed: "Failed",
};

/** Map machine states to the canonical product-loop stage. */
export const UPLOAD_STATE_TO_STAGE: Record<UploadState, string> = {
  idle: "upload",
  selecting: "upload",
  presigning: "upload",
  uploading: "upload",
  uploaded: "upload",
  analyzing: "analysis",
  ranking: "ranking",
  directing: "directing",
  rendering: "rendering",
  exporting: "exporting",
  complete: "feedback",
  failed: "upload",
};
