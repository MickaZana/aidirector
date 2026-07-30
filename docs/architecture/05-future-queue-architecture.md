# Future Queue Architecture

## Current State

Development uses `LocalQueue` (in-memory Map). Production uses Redis-backed RQ with four queues.

## Target Architecture

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  HTTP Request│    │  WebSocket   │    │  Cron/Schedule│
│  (API)       │    │  (real-time) │    │  (maintenance)│
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │                   │                    │
       ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────┐
│                   Queue Provider                     │
│  ┌─────────────────────────────────────────────────┐ │
│  │  BullMQ / RabbitMQ / Google PubSub              │ │
│  │  - Priority queues                              │ │
│  │  - Delayed jobs                                 │ │
│  │  - DLQ (Dead Letter Queue)                      │ │
│  │  - Job scheduling                               │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
       │           │           │           │
       ▼           ▼           ▼           ▼
┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐
│ CV   │   │ LLM  │   │Render│   │Export│
│Queue │   │Queue │   │Queue │   │Queue │
└──────┘   └──────┘   └──────┘   └──────┘
```

## Migrating from LocalQueue to BullMQ

1. Implement `QueueProvider` using BullMQ
2. Replace in `services/index.ts`:
   ```typescript
   import { BullMQQueue } from "@/services/processingQueue/BullMQQueue";
   const queueProvider: QueueProvider = new BullMQQueue(redisUrl);
   ```
3. All consumers pick up the new queue automatically

## Why This Abstraction Matters

- **Testability**: Tests use `LocalQueue` — no Redis dependency
- **Local dev**: Zero infrastructure requirements
- **Production**: Scales to distributed workers transparently
- **Swap cost**: One import change in the service registry
