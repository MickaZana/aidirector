/**
 * Processing Queue — barrel exports.
 *
 * Usage:
 *   import { LocalQueue } from "@/services/processingQueue/LocalQueue";
 *   const queue = new LocalQueue();
 *   await queue.enqueue({ jobId: "..." });
 */

export type { QueueProvider, Job, JobStatus } from "./Provider";
export { LocalQueue } from "./LocalQueue";
