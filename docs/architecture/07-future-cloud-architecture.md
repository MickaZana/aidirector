# Future Cloud Architecture

## Current Production Topology

```
┌─────────────────────────────────────────────────────┐
│                    Cloudflare                        │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  R2 Storage   │  │  DNS + CDN   │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                     Vercel                           │
│  ┌────────────────────────────────────────────────┐ │
│  │  Next.js Frontend (auto-deployed from main)    │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                     Modal                            │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  GPU Workers  │  │  CPU Workers │                 │
│  │  (CV, LLM)    │  │  (Render)    │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                  Managed Services                    │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐  │
│  │  Neon    ││ Upstash  ││  Clerk   ││  Stripe  │  │
│  │ Postgres ││  Redis   ││   Auth   ││ Billing  │  │
│  └──────────┘└──────────┘└──────────┘└──────────┘  │
└─────────────────────────────────────────────────────┘
```

## Future Target Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Load Balancer                      │
│                      (Cloudflare)                     │
└────────────────────┬─────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐   ┌──────────────────┐
│  API Instance 1  │   │  API Instance 2  │
│  (Docker/Fly)    │   │  (Docker/Fly)    │
│  - FastAPI       │   │  - FastAPI       │
│  - Health check  │   │  - Health check  │
│  - Metrics       │   │  - Metrics       │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         ▼                      ▼
┌──────────────────────────────────────────────┐
│              Service Mesh                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │  Neon    │ │ Upstash  │ │  R2      │     │
│  │ Postgres │ │  Redis   │ │ Storage  │     │
│  └──────────┘ └──────────┘ └──────────┘     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │  Clerk   │ │  Stripe  │ │  Sentry  │     │
│  └──────────┘ └──────────┘ └──────────┘     │
└──────────────────────────────────────────────┘
```

## Scaling Strategy

| Level | API | Database | Queue | Workers |
|---|---|---|---|---|
| **MVP** | 1 container | Neon free tier | Upstash free | Modal |
| **Growth** | 2+ containers | Neon scale | Upstash pro | Modal pro |
| **Scale** | Auto-scaled | Read replicas | BullMQ cluster | Dedicated GPU |
| **Enterprise** | Multi-region | Multi-region | Multi-region | On-prem option |

## Migration Path

Each infrastructure change is provider-swap in the service registry:

1. **Storage**: `LocalStorageProvider` → `R2StorageProvider` (current: presigned URLs)
2. **Queue**: `LocalQueue` → `BullMQQueue` (future: when Redis-backed workers are needed)
3. **Workers**: In-process → Modal (current) → Dedicated GPU (future)
