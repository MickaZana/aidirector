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

import modal
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
    """Re-evaluate an existing export's features against whatever
    engagement_events currently exist in the DB.

    Pipeline:
      1. Load ExportArtifact + resolve owning job (via
         ExportArtifact → RenderOutput → RenderJob → Job).
      2. Aggregate existing engagement_events for the export.
      3. Evaluate derived features (maturity, confidence, score).
      4. Persist a new PerformanceFeatureSet row (upsert by
         (export_id, feature_version)).
      5. Return the new feature set summary.
    """
    import uuid as _uuid

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import (
        ExportArtifact,
        Job,
        RenderJob,
        RenderOutput,
    )
    from api.services.engagement_aggregation import aggregate_engagement_for_export
    from api.services.evaluation_layer import evaluate_export, persist_features

    assert engine is not None, "DATABASE_URL must be set"

    with Session(engine) as db:
        artifact = db.execute(
            select(ExportArtifact).where(ExportArtifact.id == _uuid.UUID(export_id))
        ).scalar_one_or_none()
        if artifact is None:
            raise ValueError(f"ExportArtifact {export_id} not found")

        # Resolve the owning job
        ro = db.execute(
            select(RenderOutput).where(RenderOutput.id == artifact.render_output_id)
        ).scalar_one_or_none()
        rj = (
            db.execute(
                select(RenderJob).where(RenderJob.id == ro.render_job_id)
            ).scalar_one_or_none()
            if ro
            else None
        )
        job = (
            db.execute(select(Job).where(Job.id == rj.job_id)).scalar_one_or_none() if rj else None
        )
        job_id = job.id if job else None

        # Aggregate (reads engagement_events from DB)
        agg = aggregate_engagement_for_export(db, export_id=artifact.id)

        # Evaluate derived features (maturity, confidence, score)
        features = evaluate_export(
            db,
            export=artifact,
            aggregation=agg,
        )

        # Persist as PerformanceFeatureSet (upsert by export_id + version)
        row = persist_features(db, features=features, job_id=job_id)
        db.commit()

        return {
            "export_id": export_id,
            "feature_set_id": str(row.id),
            "feature_version": row.feature_version,
            "maturity_state": row.maturity_state,
            "engagement_confidence": row.engagement_confidence,
            "engagement_score": row.engagement_score,
            "total_events_seen": agg.total_events_seen,
        }


# ---------------------------------------------------------------------------
# Re-evaluation cron — sweeps exports that need maturity re-assessment
# ---------------------------------------------------------------------------


@app.function(
    image=intel_image,
    secrets=secrets,
    timeout=600,
    memory=2048,
    schedule=modal.Cron("0 */4 * * *"),  # every 4 hours
)
def re_evaluate_maturing_exports() -> dict:
    """Periodically re-evaluate exports that have progressed in maturity.

    An export's MaturityState transitions FRESH → MATURING → STABLE →
    DECAYED based on age and sample size. When it crosses a threshold,
    the confidence weight changes (0.2 → 0.6 → 1.0 → 0.7), which means
    the engagement score used by the ranker may change materially.

    This cron finds exports whose last evaluation was before their
    maturity state likely changed, re-evaluates them, and persists the
    updated feature set.

    Schedule: every 4 hours (conservative — avoids thundering herd).
    """
    import logging

    log = logging.getLogger(__name__)
    log.info("re_evaluate_maturing_exports: starting sweep")

    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from api.db import engine
    from api.models import ExportArtifact, PerformanceFeatureSet
    from api.services.evaluation_layer import MaturityState, _classify_maturity

    assert engine is not None, "DATABASE_URL must be set"

    results: list[dict] = []
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=1)  # only exports > 1 hour old (past FRESH)

    with Session(engine) as db:
        # Find exports whose last evaluation is stale relative to their age.
        # We select all exports older than 1 hour that have engagement events,
        # then check if their maturity state would have changed.
        exports = (
            db.execute(select(ExportArtifact).where(ExportArtifact.created_at < cutoff))
            .scalars()
            .all()
        )

        evaluated = 0
        for export in exports:
            try:
                # Find the latest feature set for this export
                latest_fs = db.execute(
                    select(PerformanceFeatureSet)
                    .where(PerformanceFeatureSet.export_id == export.id)
                    .order_by(PerformanceFeatureSet.evaluated_at.desc())
                ).scalar_one_or_none()

                age_hours = (
                    now - export.created_at.replace(tzinfo=timezone.utc)
                    if export.created_at.tzinfo is None
                    else now - export.created_at
                ).total_seconds() / 3600.0

                current_maturity = _classify_maturity(
                    age_hours=max(0, age_hours),
                    sample_size=_estimate_sample_size(db, export.id),
                )

                # Skip if maturity hasn't changed from last evaluation
                if latest_fs and latest_fs.maturity_state == current_maturity.value:
                    continue

                # Re-evaluate
                result = evaluate_export_now.remote(str(export.id), str(export.tenant_id)[:8])
                results.append(result)
                evaluated += 1
                log.info(
                    "re_evaluate: export=%s maturity=%s -> %s score=%s",
                    export.id,
                    latest_fs.maturity_state if latest_fs else "NONE",
                    current_maturity.value,
                    result.get("engagement_score"),
                )
            except Exception as exc:
                log.warning("re_evaluate: export=%s failed: %s", export.id, exc)
                continue

    summary = {
        "exports_scanned": len(exports),
        "exports_re_evaluated": evaluated,
        "results": results,
    }
    log.info("re_evaluate_maturing_exports: sweep complete %s", summary)
    return summary


def _estimate_sample_size(db, export_id: str) -> int:
    """Quick sample-size estimate from engagement_events table."""
    from sqlalchemy import func
    from sqlalchemy.orm import Session
    from api.models import EngagementEvent

    count = db.execute(
        select(func.count(EngagementEvent.id)).where(EngagementEvent.export_id == export_id)
    ).scalar()
    return count or 0
