# Upload Flow

## End-to-End Upload Sequence

```
User        Browser          API              R2          Workers
 │            │               │               │            │
 │ 1. Select  │               │               │            │
 │   file     │               │               │            │
 │───────────>│               │               │            │
 │            │ 2. POST        │               │            │
 │            │    /api/uploads│               │            │
 │            │    /presign    │               │            │
 │            │──────────────>│               │            │
 │            │               │ 3. Generate   │            │
 │            │               │    presigned  │            │
 │            │               │    PUT URL    │            │
 │            │<──────────────│               │            │
 │            │ 4. PUT file   │               │            │
 │            │    to presigned URL           │            │
 │            │──────────────────────────────>│            │
 │            │ 5. Progress events            │            │
 │            │<──────────────────────────────│            │
 │            │ 6. POST        │               │            │
 │            │    /api/uploads│               │            │
 │            │    /:id/       │               │            │
 │            │    complete    │               │            │
 │            │──────────────>│               │            │
 │            │               │ 7. Create job │            │
 │            │               │───────────────┼───────────>│
 │            │               │               │            │
```

## Upload State Machine (Client Side)

```
idle → selecting → presigning → uploading → uploaded
                                              ↓
                                     analyzing → ranking → directing →
                                     rendering → exporting → complete
                                              ↓
                                             failed
```

Defined in `services/state-machines/upload-machine.ts` as a pure reducer.

## Key Design Decisions

1. **Presigned URLs** — Files are uploaded directly to R2. The API never handles raw file bytes.

2. **Progress tracking** — Uses `XMLHttpRequest` (not `fetch`) for reliable `upload.onprogress` events.

3. **Client-side queue** — `stores/upload-queue.ts` manages up to 12 concurrent uploads with per-entry state machines.

4. **Idempotency** — Each upload has a deterministic SHA256 hash. Duplicate uploads are silently deduplicated.

5. **Storage abstraction** — All storage operations go through `StorageProvider` (`services/storage/`). The current `LocalStorageProvider` is for development; production uses R2 via presigned URLs.
