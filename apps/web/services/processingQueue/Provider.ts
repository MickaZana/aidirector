/**
 * Processing Queue Provider interface.
 *
 * Abstracts job queueing so that the application never depends directly on
 * Redis, Bull, RabbitMQ, or any other queue implementation. Swap providers
 * by changing a single import at the service-registry level.
 *
 * Implementations:
 *   - LocalQueue          (development, in-memory)
 *   - RedisQueue          (future: Upstash Redis / BullMQ)
 */

export type JobStatus =
  | "queued"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled";

export interface Job<T = unknown> {
  /** Unique job identifier */
  id: string;
  /** The job payload */
  data: T;
  /** Current status */
  status: JobStatus;
  /** ISO-8601 timestamp of when the job was enqueued */
  createdAt: string;
  /** ISO-8601 timestamp of last status change */
  updatedAt: string;
  /** Number of retry attempts so far */
  attempts: number;
  /** Maximum number of retry attempts */
  maxAttempts: number;
  /** Error message if the job failed */
  error?: string;
  /** Optional progress percentage (0–100) */
  progress?: number;
}

export interface QueueProvider {
  /**
   * Enqueue a new job for processing.
   * @param job - The job data payload
   * @param options - Optional queueing options (priority, delay, etc.)
   * @returns The created Job object
   */
  enqueue<T>(job: T, options?: { maxAttempts?: number; priority?: number }): Promise<Job<T>>;

  /**
   * Cancel a pending or in-progress job.
   * @param jobId - The job's unique identifier
   */
  cancel(jobId: string): Promise<void>;

  /**
   * Get the current status of a job.
   * @param jobId - The job's unique identifier
   * @returns The Job object, or null if not found
   */
  status<T = unknown>(jobId: string): Promise<Job<T> | null>;

  /**
   * Retry a failed job.
   * @param jobId - The job's unique identifier
   * @returns The updated Job object
   */
  retry<T = unknown>(jobId: string): Promise<Job<T>>;

  /**
   * List all jobs, optionally filtered by status.
   * @param statusFilter - Optional status to filter by
   */
  list<T = unknown>(statusFilter?: JobStatus): Promise<Job<T>[]>;
}
