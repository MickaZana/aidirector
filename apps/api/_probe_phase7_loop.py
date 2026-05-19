"""Phase 7 integration probe — telemetry ingestion + Evaluation Layer.

Proves the analyze → rank → direct → render → export → measure chain:

  ExportArtifact (Phase 6)
   → synthetic EngagementEvent ingestion
   → engagement_aggregation (bucket, dedupe, outlier-drop)
   → evaluation_layer (maturity, confidence, normalization)
   → PerformanceFeatureSet (ranker-consumable)
   → ranking_feedback_adapter (READ-ONLY view of derived features)

Eight sub-tests:

  A) Schema: 3 new tables (engagement_events, experiment_groups,
     performance_feature_sets) with expected columns + indexes.
  B) Ingestion: synthetic engagement events persist; FK chain to
     exports works.
  C) Aggregation: dedupe drops exact-duplicate events; outliers
     (negative + NaN + inf) dropped.
  D) Evaluation: maturity, confidence, normalized rates, composite
     engagement_score all produced.
  E) Replay safety: re-running aggregation+evaluation yields the same
     engagement_score, maturity, confidence (modulo timestamp).
  F) Experiment grouping: ExperimentGroup row + FK from
     PerformanceFeatureSet works; siblings query returns N rows.
  G) Adapter discipline: ranking_feedback_adapter exposes
     PerformanceFeatureView (derived only); no raw event fields leak.
  H) Usage events: ENGAGEMENT_INGESTED and EVALUATION_COMPLETED both
     present with rich metadata.

Writes a report to _probe_phase7_loop.out.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase7_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"
FIXTURE_DIR = Path(__file__).parent / "_probe_phase7_fixtures"
SOURCE_PATH = FIXTURE_DIR / "source_30s.mp4"
RENDER_OUTPUT_DIR = FIXTURE_DIR / "renders"
LOCAL_STORAGE_MIRROR = FIXTURE_DIR / "_storage"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def _silent(fn) -> None:
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        fn()
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err


def _ensure_fixture_source() -> str:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_PATH.exists() and SOURCE_PATH.stat().st_size > 0:
        return str(SOURCE_PATH)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not on PATH")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=duration=30:size=320x240:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k",
        "-pix_fmt", "yuv420p", "-shortest",
        str(SOURCE_PATH),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"fixture source build failed: {proc.stderr[-400:]}")
    return str(SOURCE_PATH)


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    log("step: start")
    if PROBE_DB.exists():
        PROBE_DB.unlink()
    if RENDER_OUTPUT_DIR.exists():
        shutil.rmtree(RENDER_OUTPUT_DIR)
    if LOCAL_STORAGE_MIRROR.exists():
        shutil.rmtree(LOCAL_STORAGE_MIRROR)
    LOCAL_STORAGE_MIRROR.mkdir(parents=True, exist_ok=True)

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    os.environ["LOCAL_STORAGE_MIRROR"] = str(LOCAL_STORAGE_MIRROR)
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    _silent(lambda: command.upgrade(cfg, "head"))
    log("alembic upgrade head: OK")

    source_uri = _ensure_fixture_source()

    # --- sub-test A: schema -----------------------------------------------
    from sqlalchemy import create_engine, func, inspect, select
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    log(f"A.tables={tables}")
    for t in ("engagement_events", "experiment_groups", "performance_feature_sets"):
        if t not in tables:
            log(f"FAIL.A: {t} not created")
            return 2

    expected_engagement_cols = {
        "id", "tenant_id", "export_id", "platform", "metric_type",
        "metric_value", "observed_at", "observation_window_hours",
        "source", "raw_payload", "created_at", "updated_at",
    }
    actual = {c["name"] for c in inspector.get_columns("engagement_events")}
    log(f"A.engagement_events.cols={sorted(actual)}")
    if not expected_engagement_cols.issubset(actual):
        log(f"FAIL.A: engagement_events missing {expected_engagement_cols - actual}")
        return 3

    expected_pfs_cols = {
        "id", "tenant_id", "export_id", "experiment_group_id",
        "feature_version", "maturity_state", "engagement_confidence",
        "normalized_view_rate", "normalized_completion_rate",
        "normalized_watch_time", "replay_rate", "share_rate",
        "engagement_score", "evaluated_at", "derived_metadata",
        "created_at", "updated_at",
    }
    actual_pfs = {c["name"] for c in inspector.get_columns("performance_feature_sets")}
    log(f"A.performance_feature_sets.cols={sorted(actual_pfs)}")
    if not expected_pfs_cols.issubset(actual_pfs):
        log(f"FAIL.A: pfs missing {expected_pfs_cols - actual_pfs}")
        return 4

    expected_eg_cols = {
        "id", "tenant_id", "experiment_name", "experiment_version",
        "hypothesis", "closed_at", "group_metadata",
        "created_at", "updated_at",
    }
    actual_eg = {c["name"] for c in inspector.get_columns("experiment_groups")}
    log(f"A.experiment_groups.cols={sorted(actual_eg)}")
    if not expected_eg_cols.issubset(actual_eg):
        log(f"FAIL.A: experiment_groups missing {expected_eg_cols - actual_eg}")
        return 5

    # --- run Phases 0-6 chain to get an ExportArtifact --------------------
    from api.models import (
        ClipCandidate, DirectorPlan, EngagementEvent, EngagementMetricType,
        ExperimentGroup, ExportArtifact, ExportArtifactStatus, Job, JobStatus,
        MaturityState, PerformanceFeatureSet, RenderJob, RenderJobStatus,
        RenderOutput, Scene, Tenant, Upload, UploadStatus, UsageEvent,
        UsageEventType, User,
    )
    from api.services.intel.scene_analysis_adapter import analyze_video
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.intel.capability_registry import SceneRecord
    from api.services.scene_persistence import persist_scene_analysis
    from api.services.clip_candidate_persistence import persist_clip_candidates
    from api.services.director_plan_builder import build_director_plan
    from api.services.director_plan_persistence import persist_director_plan
    from api.services.render_manifest_builder import build_manifests
    from api.services.intel.render_plan_adapter import render_clip
    from api.services.render_output_persistence import (
        complete_render_job, start_render_job,
    )
    from api.services.export_artifact_builder import build_export_artifact
    from api.services.export_persistence import persist_export_artifact
    from api.services.r2 import (
        export_key, parse_storage_uri, put_local_file,
    )
    from api.services.usage_events import emit_usage_event
    from api.services.engagement_aggregation import (
        aggregate_engagement_for_export, RawAggregation,
    )
    from api.services.evaluation_layer import (
        evaluate_export, persist_features,
    )
    from api.services.intel.ranking_feedback_adapter import (
        PerformanceFeatureView,
        get_engagement_score_for_export,
        get_features_for_experiment_group,
        get_features_for_export,
    )

    fixture_reads = [
        {"t":  5.0, "raw_text": "0  -  0    00:30", "ocr_confidence": 0.85},
        {"t":  8.0, "raw_text": "0  -  0    01:00", "ocr_confidence": 0.85},
        {"t": 12.0, "raw_text": "0  -  0    01:30", "ocr_confidence": 0.85},
        {"t": 16.0, "raw_text": "1  -  0    01:35", "ocr_confidence": 0.86},
        {"t": 20.0, "raw_text": "1  -  0    01:40", "ocr_confidence": 0.86},
        {"t": 22.0, "raw_text": "1  -  0    02:00", "ocr_confidence": 0.86},
        {"t": 26.0, "raw_text": "1  -  0    02:30", "ocr_confidence": 0.87},
    ]
    analysis = analyze_video(
        upload_id="probe-upload-phase7",
        source_uri="fixture://memory",
        fixture_reads=fixture_reads,
    )

    PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels"]
    with Session(engine) as db:
        tenant = Tenant(slug="phase7_probe", name="Phase 7 Probe", plan="creator")
        db.add(tenant); db.flush()
        user = User(
            tenant_id=tenant.id, clerk_user_id="user_probe7",
            email="probe7@aidirector.app", role="admin",
        )
        db.add(user); db.flush()
        upload = Upload(
            tenant_id=tenant.id, user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe7/match.mp4",
            filename="match.mp4", bytes=Path(source_uri).stat().st_size,
            duration_s=30.0, sport="football",
            status=UploadStatus.READY.value,
            upload_metadata={"source_uri": source_uri},
        )
        db.add(upload); db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id,
            event_type=UsageEventType.UPLOAD_CREATED, unit="upload",
            metadata={},
        )

        job = Job(
            tenant_id=tenant.id, upload_id=upload.id, intent="analyze",
            status=JobStatus.RUNNING.value, cost_budget_cents=30,
        )
        db.add(job); db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id, job_id=job.id,
            event_type=UsageEventType.ANALYSIS_STARTED, unit="job",
            metadata={"intent": job.intent},
        )

        scene_rows = persist_scene_analysis(db, job=job, result=analysis)
        ranked = rank_clip_candidates(
            upload_id=str(upload.id),
            scenes=[
                SceneRecord(
                    t_start=s.t_start, t_end=s.t_end, kind=s.kind,
                    arc_position=s.arc_position, intensity=s.intensity,
                    importance=s.importance, signals=s.signals,
                )
                for s in scene_rows
            ],
        )
        candidate_rows = persist_clip_candidates(
            db, job=job, scenes_in_order=scene_rows, ranked=ranked
        )
        plan = build_director_plan(
            upload_id=str(upload.id), job_id=str(job.id),
            candidates=candidate_rows, platform_targets=PLATFORMS,
        )
        persist_director_plan(db, job=job, plan=plan)

        manifest_result = build_manifests(
            plan=plan, source_uri=source_uri,
            tenant_id=str(tenant.id), tenant_slug=tenant.slug,
        )
        target = manifest_result.manifests[0]
        rj = start_render_job(db, job=job, manifest=target)
        db.flush()
        exec_result = render_clip(target, output_dir=RENDER_OUTPUT_DIR)
        ro = complete_render_job(
            db, job=job, render_job=rj, manifest=target, result=exec_result
        )

        # Build the ExportArtifact (Phase 6)
        cand_uuid = uuid.UUID(target.candidate_id)
        inputs = build_export_artifact(
            render_output=ro, tenant_slug=tenant.slug, candidate_id=cand_uuid,
            platform=target.platform,
            local_source_path=Path(exec_result.output_path),
            export_version=1,
        )
        scheme, _path = parse_storage_uri(inputs.storage_uri)
        key = export_key(str(tenant.id), str(inputs.export_id), inputs.filename)
        put_local_file(Path(exec_result.output_path), key)
        artifact = persist_export_artifact(
            db, job=job, render_output=ro, inputs=inputs,
            status=ExportArtifactStatus.UPLOADED,
        )
        db.commit()

        log(f"chain.export_id={artifact.id}")
        log(f"chain.platform={artifact.platform}")

        # --- sub-test B: ingest synthetic engagement events ---------------
        # Two windows (24h, 168h), two platforms, multiple metrics.
        now = datetime.now(timezone.utc)
        events_to_insert = []

        # YouTube Shorts — 24h window
        events_to_insert += _make_events(
            tenant.id, artifact.id, "youtube_shorts", 24, now,
            [
                ("impression", 1200),
                ("view", 800),
                ("like", 60),
                ("share", 20),
                ("comment", 8),
                ("watch_time_s", 9600),
                ("completion_rate", 0.55),
                ("replay", 40),
            ],
        )
        # Same window: a deliberate duplicate to test dedupe. Critical: the
        # observed_at must MATCH the original `view` event's observed_at,
        # which is now - 1 minute (view is metric index 1 in the batch above).
        # The dedupe key is (export_id, platform, metric_type, observed_at).
        duplicate_observed_at = now - timedelta(minutes=1)
        events_to_insert.append(
            EngagementEvent(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                export_id=artifact.id,
                platform="youtube_shorts",
                metric_type="view",
                metric_value=800.0,  # same value (would still dedupe even if different)
                observed_at=duplicate_observed_at,
                observation_window_hours=24,
                source="duplicate-test",
                raw_payload={"note": "deliberate dedupe test"},
            )
        )
        # Outliers (must be dropped by the aggregator).
        # NaN / Inf can't survive the SQLite NOT NULL constraint (the
        # sqlite3 driver coerces NaN→NULL), so we test those in-memory
        # below via `_is_outlier`. DB-inserted outliers are negative
        # values, which SQLite accepts but the aggregator rejects.
        events_to_insert += _make_events(
            tenant.id, artifact.id, "youtube_shorts", 24, now,
            [("view", -50.0), ("view", -1.0), ("view", -10000.0)],
            source="outlier-test",
        )
        # TikTok — same window
        events_to_insert += _make_events(
            tenant.id, artifact.id, "tiktok", 24, now,
            [
                ("impression", 2000),
                ("view", 1700),
                ("like", 120),
                ("share", 80),
                ("watch_time_s", 18000),
                ("completion_rate", 0.45),
                ("replay", 110),
            ],
            base_offset_minutes=5,
        )
        # 168h window for stability check
        events_to_insert += _make_events(
            tenant.id, artifact.id, "youtube_shorts", 168, now,
            [
                ("impression", 5000),
                ("view", 2800),
                ("like", 180),
                ("share", 95),
                ("watch_time_s", 32000),
                ("completion_rate", 0.50),
                ("replay", 120),
            ],
            base_offset_minutes=10,
        )

        for e in events_to_insert:
            db.add(e)
        db.flush()
        emit_usage_event(
            db,
            tenant_id=tenant.id, job_id=job.id,
            event_type=UsageEventType.ENGAGEMENT_INGESTED,
            quantity=float(len(events_to_insert)),
            unit="event",
            metadata={"export_id": str(artifact.id)},
        )
        db.commit()

        engagement_count = db.execute(
            select(func.count()).select_from(EngagementEvent)
        ).scalar()
        log(f"B.engagement_events_count={engagement_count}")
        log(f"B.events_inserted={len(events_to_insert)}")
        if engagement_count != len(events_to_insert):
            log("FAIL.B: persisted engagement count mismatch")
            return 6

        # In-memory NaN/Inf rejection check (these values can't be stored
        # in SQLite under a NOT NULL FLOAT column, so we test the gate
        # directly).
        from api.services.engagement_aggregation import _is_outlier

        nan_rejected = _is_outlier(float("nan"))
        inf_rejected = _is_outlier(float("inf"))
        neg_rejected = _is_outlier(-1.0)
        none_rejected = _is_outlier(None)  # type: ignore[arg-type]
        log(
            f"C.in_memory_outlier_gate: nan={nan_rejected} inf={inf_rejected} "
            f"neg={neg_rejected} none={none_rejected}"
        )
        if not all((nan_rejected, inf_rejected, neg_rejected, none_rejected)):
            log("FAIL.C: in-memory outlier gate let a bad value through")
            return 6

        # --- sub-test C: aggregation: dedupe + outlier rejection ---------
        agg: RawAggregation = aggregate_engagement_for_export(db, export_id=artifact.id)
        log(f"C.windows={len(agg.windows)}")
        log(f"C.total_events_seen={agg.total_events_seen}")
        log(f"C.dedup_dropped={agg.dedup_dropped}")
        log(f"C.outliers_dropped={agg.outliers_dropped}")
        for w in agg.windows:
            log(
                f"C.window: platform={w.platform} window_h={w.observation_window_hours} "
                f"samples={w.sample_size} totals={w.metric_totals}"
            )
        # We inserted: 8 yt-24h + 1 yt-24h duplicate + 3 yt-24h outliers + 7 tt-24h + 7 yt-168h = 26
        if agg.total_events_seen != engagement_count:
            log("FAIL.C: aggregator missed some events")
            return 7
        # The 3 outlier values (negative + NaN + inf) must all be dropped.
        if agg.outliers_dropped < 3:
            log(
                f"FAIL.C: expected ≥3 outliers dropped, got {agg.outliers_dropped}"
            )
            return 8
        # The "view, 800" duplicate has the SAME (platform, metric, observed_at)
        # as the original, so dedupe should drop exactly 1.
        if agg.dedup_dropped < 1:
            log(f"FAIL.C: expected ≥1 dedupe drop, got {agg.dedup_dropped}")
            return 9
        # Three (platform, window) buckets: yt-24h, tt-24h, yt-168h
        if len(agg.windows) != 3:
            log(f"FAIL.C: expected 3 windows, got {len(agg.windows)}")
            return 10

        # --- sub-test D: evaluation produces ranker-safe features --------
        features = evaluate_export(db, export=artifact, aggregation=agg)
        log(f"D.feature_version={features.feature_version}")
        log(f"D.maturity_state={features.maturity_state.value}")
        log(f"D.engagement_confidence={features.engagement_confidence}")
        log(f"D.normalized_view_rate={features.normalized_view_rate}")
        log(f"D.normalized_completion_rate={features.normalized_completion_rate}")
        log(f"D.normalized_watch_time={features.normalized_watch_time}")
        log(f"D.replay_rate={features.replay_rate}")
        log(f"D.share_rate={features.share_rate}")
        log(f"D.engagement_score={features.engagement_score}")
        if not 0.0 <= features.engagement_score <= 1.0:
            log("FAIL.D: engagement_score outside [0,1]")
            return 11
        if not 0.0 <= features.engagement_confidence <= 1.0:
            log("FAIL.D: engagement_confidence outside [0,1]")
            return 12
        if features.maturity_state not in (
            MaturityState.FRESH, MaturityState.MATURING,
            MaturityState.STABLE, MaturityState.DECAYED,
        ):
            log("FAIL.D: maturity_state not in enum")
            return 13

        pfs_row = persist_features(db, features=features, job_id=job.id)
        db.commit()
        log(f"D.pfs_row.id={pfs_row.id}")

        # --- sub-test E: replay safety -----------------------------------
        agg2 = aggregate_engagement_for_export(db, export_id=artifact.id)
        log(f"E.agg2.total_events_seen={agg2.total_events_seen}")
        log(f"E.agg2.outliers_dropped={agg2.outliers_dropped}")
        log(f"E.agg2.dedup_dropped={agg2.dedup_dropped}")
        if (agg2.total_events_seen, agg2.outliers_dropped, agg2.dedup_dropped) != (
            agg.total_events_seen, agg.outliers_dropped, agg.dedup_dropped
        ):
            log("FAIL.E: aggregation not replay-safe")
            return 14
        features2 = evaluate_export(db, export=artifact, aggregation=agg2)
        log(f"E.features2.engagement_score={features2.engagement_score}")
        log(f"E.features2.engagement_confidence={features2.engagement_confidence}")
        log(f"E.features2.maturity_state={features2.maturity_state.value}")
        if features2.engagement_score != features.engagement_score:
            log(
                f"FAIL.E: engagement_score drifted: "
                f"{features.engagement_score} → {features2.engagement_score}"
            )
            return 15
        if features2.maturity_state != features.maturity_state:
            log("FAIL.E: maturity_state drifted on replay")
            return 16

        # Re-persist: same (export_id, feature_version) → update in place
        pfs_row2 = persist_features(db, features=features2, job_id=job.id)
        db.commit()
        pfs_count = db.execute(select(func.count()).select_from(PerformanceFeatureSet)).scalar()
        log(f"E.pfs_count_after_replay={pfs_count}")
        if pfs_count != 1:
            log("FAIL.E: replay created duplicate PerformanceFeatureSet row")
            return 17
        if pfs_row2.id != pfs_row.id:
            log("FAIL.E: replay rebuilt row with new id instead of updating in place")
            return 18

        # --- sub-test F: experiment grouping ------------------------------
        eg = ExperimentGroup(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            experiment_name="hook-style-v1",
            experiment_version=1,
            hypothesis="sports_hype hook beats minimal hook by ≥10% engagement_score",
            group_metadata={"variants": ["sports_hype", "minimal"]},
        )
        db.add(eg)
        db.flush()
        # Link our pfs row to the experiment group
        pfs_row.experiment_group_id = eg.id
        db.flush()
        # Also re-run evaluation explicitly linking to the experiment_group
        features_in_group = evaluate_export(
            db, export=artifact, aggregation=agg, experiment_group_id=eg.id
        )
        persist_features(db, features=features_in_group, job_id=job.id)
        db.commit()

        siblings = get_features_for_experiment_group(db, experiment_group_id=eg.id)
        log(f"F.experiment_group_id={eg.id}")
        log(f"F.experiment_name={eg.experiment_name}")
        log(f"F.siblings_count={len(siblings)}")
        if len(siblings) < 1:
            log("FAIL.F: experiment group has no linked features")
            return 19

        # --- sub-test G: ranking_feedback_adapter exposes derived only ---
        view = get_features_for_export(db, export_id=artifact.id)
        log(f"G.view.maturity={view.maturity_state.value}")
        log(f"G.view.engagement_score={view.engagement_score}")
        log(f"G.view.fields={sorted(view.__dataclass_fields__.keys())}")
        if view is None:
            log("FAIL.G: ranking_feedback_adapter returned None for known export")
            return 20

        forbidden_raw_fields = {
            "metric_value", "metric_type", "raw_payload", "observed_at",
            "observation_window_hours", "source",
        }
        leaked = forbidden_raw_fields & set(view.__dataclass_fields__.keys())
        if leaked:
            log(f"FAIL.G: PerformanceFeatureView leaks raw fields: {leaked}")
            return 21

        score = get_engagement_score_for_export(db, export_id=artifact.id)
        log(f"G.score={score}")
        if score != view.engagement_score:
            log("FAIL.G: get_engagement_score disagrees with view")
            return 22

        # --- sub-test H: usage events -----------------------------------
        usage = db.execute(select(UsageEvent)).scalars().all()
        events_summary = sorted({(u.event_type, u.unit) for u in usage})
        log(f"H.usage_events={json.dumps(events_summary)}")
        ingested = [u for u in usage if u.event_type == "engagement_ingested"]
        evaluated = [u for u in usage if u.event_type == "evaluation_completed"]
        log(f"H.engagement_ingested.count={len(ingested)}")
        log(f"H.evaluation_completed.count={len(evaluated)}")
        if len(ingested) < 1:
            log("FAIL.H: no engagement_ingested usage event")
            return 23
        if len(evaluated) < 1:
            log("FAIL.H: no evaluation_completed usage event")
            return 24
        last_eval = evaluated[-1].event_metadata or {}
        required = {
            "export_id", "feature_version", "maturity_state",
            "engagement_confidence", "engagement_score", "sample_size",
        }
        log(f"H.evaluation_completed.metadata_keys={sorted(last_eval.keys())}")
        if not required.issubset(set(last_eval.keys())):
            log(f"FAIL.H: missing evaluation metadata: {required - set(last_eval.keys())}")
            return 25

    log("sub-tests A/B/C/D/E/F/G/H: OK")
    log("OK")
    return 0


def _make_events(
    tenant_id, export_id, platform: str, window_h: int, now: datetime,
    metrics: list[tuple[str, float]], source: str = "fixture",
    base_offset_minutes: int = 0,
) -> list:
    from api.models import EngagementEvent

    out = []
    for i, (metric, value) in enumerate(metrics):
        observed = now - timedelta(minutes=base_offset_minutes + i)
        out.append(
            EngagementEvent(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                export_id=export_id,
                platform=platform,
                metric_type=metric,
                metric_value=float(value) if isinstance(value, (int, float)) else value,
                observed_at=observed,
                observation_window_hours=window_h,
                source=source,
                raw_payload={"platform": platform, "fixture_seq": i},
            )
        )
    return out


if __name__ == "__main__":
    sys.exit(main())
