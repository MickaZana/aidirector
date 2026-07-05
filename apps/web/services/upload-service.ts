/**
 * Upload service — orchestrates the file upload pipeline.
 *
 * Drives each queue entry through the state machine: presign → upload →
 * complete → create job. Progress events (UPLOAD_PROGRESS) are dispatched
 * during the R2 upload so the UI can show a real progress bar.
 *
 * All async work happens here. The UploadStudio component and the queue
 * store only manage UI state; they never call API endpoints directly.
 */

import type { Endpoints } from "@/lib/api/endpoints";
import type { UploadDispatchFn } from "@/stores/upload-queue";

/**
 * Process one queue entry: presign → upload → complete → create job.
 *
 * Dispatches state-machine events on the queue entry as each step
 * completes. Returns when the pipeline reaches "analyzing" (the rest
 * is driven by backend workers and job-event polling).
 */
export async function processUpload(
  endpoints: Endpoints,
  entryId: string,
  file: File,
  sport: string,
  dispatch: UploadDispatchFn,
): Promise<void> {
  // ── 1. Presign ────────────────────────────────────────────────────────
  dispatch(entryId, { type: "PRESIGN_REQUESTED" });

  let presignResult: { upload_id: string; url: string };
  try {
    presignResult = await endpoints.presignUpload({
      filename: file.name,
      content_type: file.type || "video/mp4",
      size_bytes: file.size,
      sport,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Presign request failed";
    dispatch(entryId, { type: "PRESIGN_FAILED", error: msg });
    return;
  }

  dispatch(entryId, {
    type: "PRESIGN_OK",
    uploadId: presignResult.upload_id,
    presignedUrl: presignResult.url,
  });

  // ── 2. Upload to R2 (with progress) ───────────────────────────────────
  try {
    await uploadFileWithProgress(presignResult.url, file, (bytesUploaded) => {
      dispatch(entryId, { type: "UPLOAD_PROGRESS", bytesUploaded });
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "File upload failed";
    dispatch(entryId, { type: "UPLOAD_FAILED", error: msg });
    return;
  }

  dispatch(entryId, { type: "UPLOAD_OK" });

  // ── 3. Complete upload + create job ───────────────────────────────────
  try {
    await endpoints.completeUpload(presignResult.upload_id);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Complete upload failed";
    dispatch(entryId, { type: "PIPELINE_FAILED", error: msg, stage: "uploaded" });
    return;
  }

  try {
    await endpoints.createJob({
      upload_id: presignResult.upload_id,
      intent: "analyze",
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : "Job creation failed";
    dispatch(entryId, { type: "PIPELINE_FAILED", error: msg, stage: "uploaded" });
    return;
  }

  // Front-end pipeline states after this point are driven by backend
  // workers and reflected via job-event polling.
  dispatch(entryId, { type: "ANALYSIS_STARTED" });
}

/**
 * Upload a file to a presigned R2 URL with progress tracking.
 * Uses XMLHttpRequest for reliable progress events.
 */
function uploadFileWithProgress(
  url: string,
  file: File,
  onProgress: (bytesUploaded: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url, true);
    xhr.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    xhr.upload.onprogress = (event: ProgressEvent) => {
      if (event.lengthComputable) {
        onProgress(event.loaded);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));
    xhr.onabort = () => reject(new Error("Upload aborted"));

    xhr.send(file);
  });
}
