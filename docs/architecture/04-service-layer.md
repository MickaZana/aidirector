# Service Layer

## Frontend Service Architecture

All frontend services are provider-based. Components access them through the `Services` registry rather than importing concrete implementations directly.

```
services/
├── index.ts                  ← Service registry (central DI)
├── analytics.ts              ← Product analytics (localStorage-backed)
├── upload-service.ts         ← Upload pipeline orchestrator
├── job-events.ts             ← Job event transport (polling/WebSocket)
├── pipeline-stages.ts        ← Pipeline stage derivation (pure functions)
├── storage/
│   ├── Provider.ts           ← StorageProvider interface
│   ├── LocalStorageProvider.ts ← Dev implementation
│   └── index.ts              ← Barrel exports
├── processingQueue/
│   ├── Provider.ts           ← QueueProvider interface
│   ├── LocalQueue.ts         ← Dev implementation
│   └── index.ts              ← Barrel exports
├── workers/
│   ├── Provider.ts           ← WorkerContract interface
│   └── index.ts              ← Barrel exports
├── notifications/
│   ├── Provider.ts           ← NotificationProvider interface
│   ├── ToastNotificationProvider.ts ← Wraps zustand toast-store
│   └── index.ts              ← Barrel exports
└── state-machines/
    ├── upload-machine.ts     ← Upload pipeline state machine
    └── render-machine.ts     ← Per-render-job state machine
```

## Service Registry

```typescript
// services/index.ts
export const Services = {
  notifications: NotificationProvider,  // ToastNotificationProvider
  storage: StorageProvider,              // LocalStorageProvider
  queue: QueueProvider,                  // LocalQueue
  analytics: Analytics,                  // Singleton analytics instance
  config: AppConfig,                     // Resolved environment config
};
```

Components import from `@/services`:

```typescript
import { Services } from "@/services";
Services.notifications.success("Upload complete");
Services.analytics.track("upload_completed", { fileSize });
```

## Backend Service Layer

```
services/
├── r2.py                  ← Storage (R2 + local fallback)
├── queue.py               ← Queue (Redis + InMemoryQueue fallback)
├── billing.py             ← Stripe billing lifecycle
├── provenance.py          ← Ed25519 signing
├── events.py              ← Redis Pub/Sub for WebSocket stream
├── state_transitions.py   ← Central state machine (single transition() entry)
├── job_view_service.py    ← JobView composite builder
├── engagement_aggregation.py ← Raw engagement aggregator
├── evaluation_layer.py    ← Derived feature evaluator
├── idempotency.py         ← Idempotency keys for render/export
├── c2pa/                  ← C2PA 2.3 provenance embedding
├── intel/                 ← AI adapter layer (OmegaClips, ranking, etc.)
└── watermarking/          ← Forensic watermarking
```

## Key Patterns

| Pattern | Description | Example |
|---|---|---|
| **Provider interface** | All external deps behind an interface | `StorageProvider`, `QueueProvider` |
| **Graceful degradation** | Fallback to in-process when remote fails | InMemoryQueue, local file storage |
| **Pure reducers** | State machines are pure functions | `reduceUpload()`, `reduceRender()` |
| **Singleton registry** | Central DI via `Services` object | `services/index.ts` |
| **Environment config** | All magic numbers in config/ | `config/index.ts` |
