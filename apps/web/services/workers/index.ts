/**
 * Workers — barrel exports.
 *
 * Currently provides only the contract interfaces. No concrete worker
 * implementations are included — those belong to the infrastructure layer
 * (Modal, Web Workers, etc.) and will be added when the queue provider is
 * swapped from LocalQueue to a distributed backend.
 *
 * Usage:
 *   import type { WorkerContract, JobHandler } from "@/services/workers";
 */

export type {
  WorkerContract,
  WorkerStatus,
  WorkerProgress,
  WorkerResult,
  WorkerStage,
  JobHandler,
} from "./Provider";
