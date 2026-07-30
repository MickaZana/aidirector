# System Overview

**AI Director** transforms long-form sports video into platform-optimised short-form clips using a pipeline of computer vision, ranking, rendering, and exporting stages.

---

## High-Level Architecture

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Upload   │ ──> │  Pipeline │ ──> │  Clips    │ ──> │  Export   │
│  Service  │     │  Workers  │     │  Gallery  │     │  Manager  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
     │                │                │                │
     ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Service Layer                             │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Storage │ │  Queue   │ │  Worker  │ │ Notification │   │
│  │Provider │ │ Provider │ │ Contract │ │  Provider    │   │
│  └─────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15 (React 19, TypeScript 5.6, Tailwind v4) |
| **API** | FastAPI (Python 3.12, Pydantic, SQLAlchemy) |
| **Database** | PostgreSQL 16 (Neon in production) |
| **Queue** | Redis 7 (Upstash in production, RQ workers) |
| **Workers** | Modal (serverless GPU/CPU) |
| **Storage** | Cloudflare R2 (S3-compatible, zero egress) |
| **Auth** | Clerk (JWT RS256, multi-tenant) |
| **Billing** | Stripe (metered, self-serve portal) |
| **CI/CD** | GitHub Actions + Pulumi IaC |
| **Observability** | Sentry + Prometheus + Logfire |

---

## Monorepo Layout

```
aidirector/
├── apps/
│   ├── api/          ← FastAPI backend (uv, Python 3.12)
│   │   ├── src/api/
│   │   │   ├── routers/      12 route modules
│   │   │   ├── services/     30+ service modules
│   │   │   ├── models/       SQLAlchemy ORM models
│   │   │   └── schemas/      Pydantic request/response schemas
│   │   ├── alembic/          9 migration scripts
│   │   └── tests/            Unit + integration tests
│   └── web/         ← Next.js frontend (pnpm, Node 20)
│       ├── app/              Next.js App Router pages
│       ├── features/         Feature-sliced page surfaces
│       ├── services/         Frontend service abstractions
│       ├── stores/           Zustand state stores
│       ├── config/           Environment-aware configuration
│       ├── components/       Shared UI components
│       └── lib/api/          Typed API client + fixtures
├── packages/
│   └── intel/        ← OmegaClips CV submodule
├── workers/          ← Worker entrypoints
├── infra/           ← Pulumi IaC (Cloudflare + Vercel + GitHub)
└── docs/            ← Architecture, runbooks, proof-of-work
```

---

## Architecture Principles

1. **Provider-based abstractions** — Every external dependency (storage, queue, workers, notifications) is behind an interface. Swap providers without changing consumers.

2. **Graceful degradation** — Every external service has a fallback. PostgreSQL down? Serve from cache. Redis down? In-process memory queue.

3. **Tenant isolation** — Every table has a `tenant_id` foreign key. All queries are scoped to the authenticated tenant.

4. **Stateless services** — All state lives in the database or queue. Services can be killed and restarted without data loss.

5. **Deterministic core** — The ranking and director-plan logic is deterministic. Same inputs always produce the same outputs.

6. **Observability first** — Every request has a unique ID. Every error is captured. Every endpoint exposes Prometheus metrics.
