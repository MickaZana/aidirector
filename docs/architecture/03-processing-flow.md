# Processing Flow

## Pipeline Stages

Once a file is uploaded, the backend processes it through 8 stages:

```
1. ANALYSIS   ── OmegaClips CV (FI-1→13): scene detection, event recognition
2. RANKING    ── Score candidates by quality, confidence, platform fit
3. DIRECTING  ── Select top clips, assign platforms, build render plan
4. RENDERING  ── FFmpeg: crop, scale, captions, title overlay
5. EXPORTING  ── Package + sign with Ed25519 provenance manifest
6. FEEDBACK   ── (optional) Apply engagement-driven score adjustment
```

## Pipeline Architecture

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   RQ      │    │  Modal   │    │   RQ     │    │  Modal   │
│  Queue    │───>│  Worker  │───>│  Queue   │───>│  Worker  │
│ q:cv      │    │ (GPU)    │    │ q:llm    │    │ (CPU)    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     ▼               ▼               ▼               ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Scene   │    │ Director │    │  Render  │    │  Export  │
│ Analysis │    │  Plan    │    │  FFmpeg  │    │  + Sign  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

## Worker Lifecycle

Every worker follows the same contract defined in `services/workers/Provider.ts`:

```
receive job → validate → process → update progress → complete → notify
```

| Stage | Description |
|---|---|
| **receive** | Pop job payload from queue |
| **validate** | Check inputs are complete and valid |
| **process** | Execute the work (CV inference, FFmpeg render, etc.) |
| **update progress** | Persist progress percentage and current stage |
| **complete** | Persist results, transition job state |
| **notify** | Emit usage event, publish to WebSocket stream |

## Job Queue Architecture (Current)

- **Provider:** Redis (Upstash in production)
- **Library:** RQ (Redis Queue)
- **Queues:** `q:cv`, `q:llm`, `q:render-cpu`, `q:export`
- **Fallback:** `InMemoryQueue` when Redis is unavailable

All queue operations go through the `QueueProvider` interface defined in `services/processingQueue/`. The current `LocalQueue` implementation is for development; Redis-backed `RQQueue` is used in production.

## Event-Driven Progress

Each stage transition emits a `UsageEvent` row. The frontend polls:

```
GET /api/jobs/{id}/events  →  { revision, last_event_at, counts }
```

When `revision` changes, the frontend refetches the full view:

```
GET /api/jobs/{id}/view    →  JobView composite
```

Future: Replace polling with WebSocket via the same `JobEventTransport` interface.
