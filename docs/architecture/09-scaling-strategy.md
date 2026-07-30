# Scaling Strategy

## Current Limits

| Resource | Current | Bottleneck |
|---|---|---|
| **Uploads** | 500 MB dev / 3 GB prod | R2 presigned URL expiry |
| **Pipeline** | 1 job at a time per tenant | Modal worker concurrency |
| **API** | 2 uvicorn workers | PostgreSQL connections (pool=10) |
| **Storage** | R2 (unlimited) | No bottleneck |
| **Queue** | Redis RQ | Single Redis instance |

## Horizontal Scaling

### API Layer

The API is stateless — scale by adding containers:

```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      replicas: 2  # → 4 → 8 as needed
```

### Database

Neon Postgres scales vertically (compute) and horizontally (read replicas):

| Stage | Plan | Connections | Storage |
|---|---|---|---|
| MVP | Free (0.5 GB) | 10 | 0.5 GB |
| Growth | Launch ($19/mo) | 100 | 10 GB |
| Scale | Scale ($69/mo) | 500 | 50 GB |

### Workers

Modal auto-scales based on queue depth. Configure per-function:

```python
@app.function(
    secrets=_modal_secrets,
    timeout=900,
    memory=4096,
    allow_concurrent_inputs=5,  # ← controls concurrency
)
```

## Performance Targets

| Metric | Current | Target |
|---|---|---|
| Upload (3 GB) | 3-5 min | 2-3 min |
| Scene analysis (90 min match) | 30s | 15s |
| Rendering (18 variants) | 2 min | 45s |
| Total pipeline | ~3 min | < 2 min |
| API p95 latency | < 200ms | < 100ms |
| API error rate | < 1% | < 0.1% |

## Cost Optimization

| Cost Center | Current | Target |
|---|---|---|
| Modal GPU | $0.36/match | $0.20/match (spot instances) |
| Neon Postgres | $19/mo | $19/mo (no change) |
| Upstash Redis | $5/mo | $5/mo (no change) |
| R2 storage | $0.015/GB/mo | $0.015/GB/mo (no change) |
| Vercel | $20/mo | $20/mo (no change) |

## Monitoring Thresholds

| Signal | Warning | Critical | Action |
|---|---|---|---|
| Error rate | > 1% | > 5% | Alert + auto-diagnose |
| p95 latency | > 500ms | > 2s | Scale API containers |
| Queue depth | > 100 | > 500 | Scale workers |
| DB connections | > 80% pool | > 95% pool | Increase pool size |
| Disk usage | > 80% | > 95% | R2 lifecycle policy |
