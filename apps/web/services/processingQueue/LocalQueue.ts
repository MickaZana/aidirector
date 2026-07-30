/**
 * LocalQueue — development-only in-memory queue backend.
 *
 * Stores jobs in a plain Map<string, Job>. Data is NOT persisted across
 * page refreshes. Suitable for development and testing only.
 *
 * For production, replace with RedisQueue (Upstash Redis / BullMQ).
 */

import type { QueueProvider, Job, JobStatus } from "./Provider";

export class LocalQueue implements QueueProvider {
  private jobs = new Map<string, Job>();

  private generateId(): string {
    return `job_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
  }

  async enqueue<T>(
    data: T,
    options?: { maxAttempts?: number; priority?: number },
  ): Promise<Job<T>> {
    const now = new Date().toISOString();
    const job: Job<T> = {
      id: this.generateId(),
      data,
      status: "queued",
      createdAt: now,
      updatedAt: now,
      attempts: 0,
      maxAttempts: options?.maxAttempts ?? 3,
      progress: 0,
    };
    this.jobs.set(job.id, job as Job);
    return job;
  }

  async cancel(jobId: string): Promise<void> {
    const job = this.jobs.get(jobId);
    if (!job) throw new Error(`LocalQueue: job "${jobId}" not found`);
    if (job.status === "completed") {
      throw new Error(`LocalQueue: cannot cancel completed job "${jobId}"`);
    }
    job.status = "cancelled";
    job.updatedAt = new Date().toISOString();
  }

  async status<T = unknown>(jobId: string): Promise<Job<T> | null> {
    const job = this.jobs.get(jobId);
    return (job as Job<T>) ?? null;
  }

  async retry<T = unknown>(jobId: string): Promise<Job<T>> {
    const job = this.jobs.get(jobId);
    if (!job) throw new Error(`LocalQueue: job "${jobId}" not found`);
    if (job.status !== "failed") {
      throw new Error(
        `LocalQueue: can only retry failed jobs, "${jobId}" is "${job.status}"`,
      );
    }
    job.status = "queued";
    job.attempts = 0;
    job.error = undefined;
    job.progress = 0;
    job.updatedAt = new Date().toISOString();
    return job as Job<T>;
  }

  async list<T = unknown>(statusFilter?: JobStatus): Promise<Job<T>[]> {
    const all = Array.from(this.jobs.values());
    if (statusFilter) {
      return all.filter((j) => j.status === statusFilter) as Job<T>[];
    }
    return all as Job<T>[];
  }

  /**
   * Simulate processing the next queued job (dev helper).
   * Moves a job from "queued" → "processing", calls the handler,
   * then moves to "completed" or "failed".
   */
  async processNext<T>(
    handler: (job: Job<T>) => Promise<void>,
  ): Promise<Job<T> | null> {
    const queued = Array.from(this.jobs.values()).filter(
      (j) => j.status === "queued",
    );
    if (queued.length === 0) return null;

    const job = queued[0];
    job.status = "processing";
    job.updatedAt = new Date().toISOString();

    try {
      await handler(job as Job<T>);
      job.status = "completed";
      job.progress = 100;
    } catch (err) {
      job.attempts += 1;
      job.error = err instanceof Error ? err.message : String(err);
      job.status = job.attempts >= job.maxAttempts ? "failed" : "queued";
    }
    job.updatedAt = new Date().toISOString();
    return job as Job<T>;
  }

  /** Remove all jobs from the queue (dev helper). */
  async clear(): Promise<void> {
    this.jobs.clear();
  }
}
