/**
 * Upload queue — ephemeral client state for files being uploaded in the
 * current session. Persisted snapshots live in the DB via the upload
 * row + usage events; this store just tracks the active flight.
 */
import { create } from "zustand";
import {
  INITIAL_UPLOAD_SNAPSHOT,
  reduceUpload,
  type UploadEvent,
  type UploadSnapshot,
} from "@/services/state-machines/upload-machine";

export interface QueueEntry {
  id: string;          // client-local UUID
  fileName: string;
  fileSize: number;
  sport: string;
  platformTargets: string[];
  snapshot: UploadSnapshot;
  createdAt: string;
}

interface UploadQueueState {
  entries: QueueEntry[];
  enqueue(input: {
    fileName: string;
    fileSize: number;
    sport: string;
    platformTargets: string[];
  }): QueueEntry;
  dispatch(id: string, event: UploadEvent): void;
  remove(id: string): void;
  clearCompleted(): void;
}

let nextId = 1;
const localId = () => `qe_${Date.now()}_${nextId++}`;

export const useUploadQueue = create<UploadQueueState>((set) => ({
  entries: [],
  enqueue(input) {
    const entry: QueueEntry = {
      id: localId(),
      fileName: input.fileName,
      fileSize: input.fileSize,
      sport: input.sport,
      platformTargets: input.platformTargets,
      snapshot: INITIAL_UPLOAD_SNAPSHOT,
      createdAt: new Date().toISOString(),
    };
    set((s) => ({ entries: [entry, ...s.entries].slice(0, 12) }));
    return entry;
  },
  dispatch(id, event) {
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, snapshot: reduceUpload(e.snapshot, event) } : e,
      ),
    }));
  },
  remove(id) {
    set((s) => ({ entries: s.entries.filter((e) => e.id !== id) }));
  },
  clearCompleted() {
    set((s) => ({
      entries: s.entries.filter(
        (e) => e.snapshot.state !== "complete" && e.snapshot.state !== "failed",
      ),
    }));
  },
}));
