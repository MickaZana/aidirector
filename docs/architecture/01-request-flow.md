# Request Flow

## Frontend → API Request Lifecycle

```
┌─────────┐     ┌───────────┐     ┌──────────┐     ┌──────────┐
│ Browser  │ ──> │ Middleware │ ──> │  Router  │ ──> │  Service │
│ (Next.js)│     │  Stack    │     │          │     │   Layer  │
└─────────┘     └───────────┘     └──────────┘     └──────────┘
     │                │                │                │
     │ 1. Request     │                │                │
     │────────────────>                │                │
     │                │ 2. Clerk JWT   │                │
     │                │    validation  │                │
     │                │────────────────>                │
     │                │                │ 3. Route match │
     │                │                │────────────────>
     │                │                │                │ 4. Business
     │                │                │                │    logic
     │                │                │                │<────────────────
     │                │                │<────────────────
     │                │<────────────────
     │<────────────────
```

## Middleware Stack (FastAPI)

Applied bottom-up (last added = first executed):

```
1. CORSMiddleware         ── CORS headers, preflight handling
2. SecurityHeadersMiddleware ── X-Content-Type-Options, X-Frame-Options, etc.
3. RequestIDMiddleware   ── Generates UUID per request, sets X-Request-ID
4. RateLimiter           ── Per-route rate limits (slowapi + Redis)
5. Exception handler     ── Structured error responses (422, 429, 500)
6. Prometheus metrics    ── Request rate, latency, error count
```

## Authentication

All authenticated routes require a Clerk JWT in the `Authorization: Bearer` header:

```python
# FastAPI dependency
async def verify_tenant(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    # 1. Extract JWT from Authorization header
    # 2. Verify RS256 signature via Clerk JWKS endpoint
    # 3. Extract org_id from JWT claims
    # 4. Upsert Tenant row (first visit creates tenant)
    # 5. Return Tenant instance
```

## Rate Limiting

- Tiered: Free (10/min), Pro (60/min), Studio (300/min)
- Keyed by tenant_id
- Returns `429 Too Many Requests` with `Retry-After` header
- Frontend catches 429 via `ApiClient` → dispatches `rate-limited` custom DOM event → `RateLimitListener` shows toast

## Error Responses

All errors follow a consistent shape:

```json
{
  "detail": {
    "type": "validation_error",
    "message": "Human-readable description",
    "code": "VALIDATION_ERROR",
    "request_id": "uuid"
  }
}
```
