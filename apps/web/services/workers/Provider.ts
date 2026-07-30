/**
 * Background Worker Contract.
 *
 * Defines the lifecycle of a background worker. Every worker follows the
 * same pipeline: receive → validate → process → update progress → complete
 * → notify. Workers are stateless; all state flows through the queue and
 * notification providers.
 *
 * Implementations:
 *   - LocalWorker           (development, runs in-process)
 *   - ModalWorker           (future: Modal serverless GPU/CPU)
 *   - WebWorker             (future: browser ServiceWorker for offline)
 */

import type { Job } from "@/services/processingQueue/Provider";

export type WorkerStatus =
  | "idle"
  | "running"
  | "paused"
  | "stopped";

export interface WorkerProgress {
  /** The job being worked on */
  jobId: string;
  /** Progress percentage (0–100) */
  progress: number;
  /** Human-readable status message */
  message: string;
  /** ISO-8601 timestamp */
  timestamp: string;
}

export interface WorkerResult {
  /** The job identifier */
  jobId: string;
  /** Whether the job completed successfully */
  success: boolean;
  /** ISO-8601 timestamp of completion */
  completedAt: string;
  /** Duration in milliseconds */
  durationMs: number;
  /** Error message if failed */
  error?: string;
  /** Arbitrary result data */
  output?: Record<string, unknown>;
}

/**
 * Worker lifecycle stages, each maps to a step in the contract:
 *
 *   receive ──→ validate ──→ process ──→ complete ──→ notify
 *                    │                       │
 *                    ↓                       ↓
 *               reject(validation)      fail(error)
 */
export type WorkerStage =
  | "received"
  | "validating"
  | "processing"
  | "completing"
  | "notifying";

/**
 * A handler that processes a single job. Implementations receive a Job
 * and a callback to report progress.
 */
export type JobHandler<T = unknown> = (
  job: Job<T>,
  onProgress: (progress: WorkerProgress) => void,
) => Promise<WorkerResult>;

export interface WorkerContract {
  /** The worker's unique name/identifier */
  readonly name: string;

  /** Current worker status */
  readonly status: WorkerStatus;

  /**
   * Start the worker. Begins processing jobs from the queue.
   * @param concurrency - Maximum number of jobs to process in parallel
   */
  start(concurrency?: number): Promise<void>;

  /**
   * Gracefully stop the worker. Finishes current jobs then exits.
   */
  stop(): Promise<void>;

  /**
   * Pause job processing. In-flight jobs continue, no new jobs are picked up.
   */
  pause(): Promise<void>;

  /**
   * Resume job processing after a pause.
   */
  resume(): Promise<void>;

  /**
   * Register a handler for a specific job type.
   * @param type    - The job type identifier
   * @param handler - The handler function
   */
  registerHandler<T>(type: string, handler: JobHandler<T>): void;

  /**
   * Get the current stage of a specific job.
   * @param jobId - The job identifier
   */
  getJobStage(jobId: string): WorkerStage | null;

  /**
   * Listen for worker events.
   */
  on(event: "progress" | "completed" | "failed" | "error", callback: (data: unknown) => void): void;
}
