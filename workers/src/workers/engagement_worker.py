"""Engagement worker — Modal-side wrapper over the evaluation layer.

Zero metric logic. Receives synthetic-or-real engagement events,
delegates ingestion + aggregation + evaluation to the services layer,
returns a result dict. Future connectors (YouTube Data API, TikTok
analytics) live OUTSIDE the worker — they call `ingest_events_fixture`
with their own payloads.

Entrypoints:
  - `ingest_events_fixture(events)` — phase 7 path
  - `evaluate_export_now(export_id, tenant_slug)` — phase 7.5 stub
"""

from __future__ import annotations

from workers.modal_app import app, intel_image, secrets


@app.function(image=intel_image, secrets=secrets, timeout=300, memory=2048)
def ingest_events_fixture(
    export_id: str,
    tenant_id: str,
    events: list[dict],
    experiment_group_id: str | None = None,
) -> dict:
    """Bulk-insert engagement events for one export and run the evaluator.

    Caller supplies normalized event dicts with platform / metric_type /
    metric_value / observed_at / observation_window_hours / source /
    raw_payload. We do schema validation on insert, then run the full
    aggregate → evaluate → persist chain.
    """
    import uuid as _uuid
    from datetime import datetime

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import (
        EngagementEvent,
        ExportArtifact,
        Job,
        RenderJob,
        RenderOutput,
        UsageEventType,
    )
    from api.services.engagement_aggregation import aggregate_engagement_for_export
    from api.services.evaluation_layer import evaluate_export, persist_features
    from api.services.usage_events import emit_usage_event

    assert engine is not None, "DATABASE_URL must be set for engagement worker"

    with Session(engine) as db:
        artifact = db.execute(
            select(ExportArtifact).where(ExportArtifact.id == _uuid.UUID(export_id))
        ).scalar_one_or_none()
        if artifact is None:
            raise ValueError(f"ExportArtifact {export_id} not found")

        # Resolve the owning job via ExportArtifact → RenderOutput → RenderJob → Job
        # chain, NOT by fetching the tenant's most-recent job (which can be wrong
        # when a tenant has multiple jobs in flight).
        ro = db.execute(
            select(RenderOutput).where(RenderOutput.id == artifact.render_output_id)
        ).scalar_one_or_none()
        if ro is None:
            raise ValueError(
                f"RenderOutput {artifact.render_output_id} not found for export {export_id}"
            )
        rj = db.execute(
            select(RenderJob).where(RenderJob.id == ro.render_job_id)
        ).scalar_one_or_none()
        if rj is None:
            raise ValueError(f"RenderJob {ro.render_job_id} not found for export {export_id}")
        job = db.execute(select(Job).where(Job.id == rj.job_id)).scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {rj.job_id} not found for export {export_id}")

        for e in events:
            row = EngagementEvent(
                id=_uuid.uuid4(),
                tenant_id=artifact.tenant_id,
                export_id=artifact.id,
                platform=e["platform"],
                metric_type=e["metric_type"],
                metric_value=float(e["metric_value"]),
                observed_at=datetime.fromisoformat(e["observed_at"]),
                observation_window_hours=int(e["observation_window_hours"]),
                source=e.get("source", "fixture"),
                raw_payload=e.get("raw_payload", {}),
            )
            db.add(row)
        db.flush()

        emit_usage_event(
            db,
            tenant_id=artifact.tenant_id,
            job_id=job.id,
            event_type=UsageEventType.ENGAGEMENT_INGESTED,
            quantity=float(len(events)),
            unit="event",
            metadata={
                "export_id": str(artifact.id),
                "source_count": len({e.get("source", "fixture") for e in events}),
                "platform_count": len({e["platform"] for e in events}),
            },
        )

        agg = aggregate_engagement_for_export(db, export_id=artifact.id)
        features = evaluate_export(
            db,
            export=artifact,
            aggregation=agg,
            experiment_group_id=(_uuid.UUID(experiment_group_id) if experiment_group_id else None),
        )
        row = persist_features(db, features=features, job_id=job.id)
        db.commit()

        return {
            "engagement_events_persisted": len(events),
            "aggregation": {
                "windows": len(agg.windows),
                "total_events_seen": agg.total_events_seen,
                "dedup_dropped": agg.dedup_dropped,
                "outliers_dropped": agg.outliers_dropped,
            },
            "feature_set": {
                "id": str(row.id),
                "feature_version": row.feature_version,
                "maturity_state": row.maturity_state,
                "engagement_confidence": row.engagement_confidence,
                "engagement_score": row.engagement_score,
            },
        }


@app.function(image=intel_image, secrets=secrets, timeout=600, memory=2048)
def evaluate_export_now(export_id: str, tenant_slug: str) -> dict:
    """Phase 7.5 stub — re-evaluate an existing export's features against
    whatever engagement_events currently exist in the DB."""
    raise NotImplementedError(
        "Phase 7.5 — periodic re-evaluation worker reads engagement_events from DB."
    )
