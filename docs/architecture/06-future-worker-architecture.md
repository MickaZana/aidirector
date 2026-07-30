# Future Worker Architecture

## Current State

Workers run on Modal (serverless GPU/CPU). Each worker follows the contract defined in `services/workers/Provider.ts`:

```
receive → validate → process → update progress → complete → notify
```

## Target Architecture

```
┌─────────────┐
│   Queue     │
│  Provider   │
└──────┬──────┘
       │ poll / push
       ▼
┌──────────────────────────────────────────────┐
│            Worker Pool                        │
│                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Worker  │  │  Worker  │  │  Worker  │   │
│  │ Instance │  │ Instance │  │ Instance │   │
│  │  (CPU)   │  │  (GPU)   │  │  (CPU)   │   │
│  └──────────┘  └──────────┘  └──────────┘   │
│                                               │
│  ┌──────────────────────────────────────┐    │
│  │  Concurrency Management              │    │
│  │  - Per-job-type concurrency limits   │    │
│  │  - Auto-scaling based on queue depth │    │
│  │  - Health checking + auto-recovery   │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

## Worker Contract

```typescript
interface WorkerContract {
  name: string;
  status: WorkerStatus;
  start(concurrency?: number): Promise<void>;
  stop(): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  registerHandler<T>(type: string, handler: JobHandler<T>): void;
  getJobStage(jobId: string): WorkerStage | null;
  on(event: "progress" | "completed" | "failed" | "error", cb: Function): void;
}
```

## Scaling Strategy

| Scale | Worker Setup | Concurrency |
|---|---|---|
| **Development** | `LocalWorker` (in-process) | 1 |
| **Beta** | Modal (serverless) | 5-10 parallel |
| **Growth** | Dedicated GPU instances | 20-50 parallel |
| **Enterprise** | Auto-scaling K8s + spot instances | 100+ parallel |

## Why This Abstraction Matters

- **Development**: Workers run in-process — no cloud dependency
- **Testing**: Worker lifecycle is testable without deploying to Modal
- **Flexibility**: Swap from Modal to dedicated infra without changing business logic
