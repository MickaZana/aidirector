"""Phase 9.5 probe — JobView composite endpoint correctness.

Seeds a complete pipeline trajectory for one tenant + job (upload → job →
scene → candidate → director_plan → render_job → render_output → export
→ feature_view → ranking_snapshot → usage_events) directly through the
ORM, then calls `build_job_view` and `build_job_events` and asserts the
composite shape matches the frontend `JobView` interface bit-for-bit.

Sub-tests (each exits with a distinct rc on failure):

  A — fresh DB seeded; build_job_view returns a JobView
  B — every collection populated; lengths match what was seeded
  C — feature_views is the 12-field projection, not raw engagement
  D — ranking snapshot fields preserve Phase 8 cap + threshold + base
  E — director_plan deserialises through the Pydantic contract
  F — tenant isolation: a foreign tenant gets None
  G — build_job_events.counts agrees with len(...) on the full view
  H — JobView serialises to JSON cleanly (FastAPI response_model path)
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase9_5_jobview.out"
PROBE_DB = Path(__file__).parent / "aidirector_phase9_5_probe.db"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    if PROBE_DB.exists():
        PROBE_DB.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    log(f"DATABASE_URL={os.environ['DATABASE_URL']}")
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    # --- run Alembic upgrade -----------------------------------------------
    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        log("ALEMBIC IMPORT FAILED:")
        log(traceback.format_exc())
        return 2

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    buf_out, buf_err = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf_out, buf_err
    try:
        command.upgrade(cfg, "head")
    except Exception:
        log("UPGRADE FAILED:")
        log(traceback.format_exc())
        return 3
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err

    log("alembic upgrade head OK")

    # --- seed pipeline ------------------------------------------------------
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from api.models import (
            ClipCandidate,
            DirectorPlan,
            ExperimentGroup,
            ExportArtifact,
            Job,
            PerformanceFeatureSet,
            RankingSnapshot,
            RenderJob,
            RenderOutput,
            Scene,
            Tenant,
            Upload,
            UsageEvent,
        )
        from api.schemas.director_plan import DIRECTOR_PLAN_VERSION
        from api.schemas.job_view import JobView as JobViewModel
        from api.services.job_view_service import build_job_events, build_job_view
    except Exception:
        log("APP IMPORT FAILED:")
        log(traceback.format_exc())
        return 4

    engine = create_engine(os.environ["DATABASE_URL"])
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()

    now = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)

    tenant_a = Tenant(id=uuid.uuid4(), slug="probe-a", name="Probe A", plan="creator")
    tenant_b = Tenant(id=uuid.uuid4(), slug="probe-b", name="Probe B", plan="creator")
    db.add_all([tenant_a, tenant_b])
    db.flush()

    upload = Upload(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        r2_key=f"tenant/{tenant_a.id}/upload/sample.mp4",
        filename="sample.mp4",
        bytes=10_000_000,
        duration_s=120.0,
        sport="football",
        status="ready",
    )
    db.add(upload)
    db.flush()

    job = Job(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        upload_id=upload.id,
        intent="analyze",
        status="succeeded",
        intel_submodule_sha="78fcd572",
        cost_budget_cents=30,
        cost_actual_cents=22,
    )
    db.add(job)
    db.flush()

    scenes = [
        Scene(
            id=uuid.uuid4(),
            job_id=job.id,
            tenant_id=tenant_a.id,
            t_start=0.0,
            t_end=18.0,
            kind="goal",
            arc_position="climax",
            intensity=0.91,
            importance=0.87,
            signals={"scoreboard_change": True},
        ),
        Scene(
            id=uuid.uuid4(),
            job_id=job.id,
            tenant_id=tenant_a.id,
            t_start=18.0,
            t_end=42.0,
            kind="build_up",
            arc_position="rising",
            intensity=0.62,
            importance=0.55,
            signals={"pass_chain": 9},
        ),
    ]
    db.add_all(scenes)
    db.flush()

    candidate = ClipCandidate(
        id=uuid.uuid4(),
        job_id=job.id,
        tenant_id=tenant_a.id,
        scene_id=scenes[0].id,
        t_start=2.0,
        t_end=14.0,
        confidence_score=0.81,
        quality_score=0.78,
        platform_score=0.73,
        rationale="Goal moment, high intensity, scoreboard delta confirmed.",
        scores={
            "base_rank_score": 0.394,
            "engagement_adjustment": 0.096,
            "final_rank_score": 0.49,
            "feedback_applied": True,
            "feature_version": "v1",
            "confidence_threshold": 0.30,
            "engagement_weight_cap": 0.15,
        },
    )
    db.add(candidate)
    db.flush()

    plan_contract = {
        "version": DIRECTOR_PLAN_VERSION,
        "upload_id": str(upload.id),
        "job_id": str(job.id),
        "model": "deterministic-builder/v1",
        "prompt_version": "v1",
        "platform_targets": ["youtube_shorts", "tiktok"],
        "selected_candidates": [
            {
                "candidate_id": str(candidate.id),
                "reason_selected": "highest final_rank_score",
                "confidence_score": 0.81,
                "quality_score": 0.78,
                "platform_score": 0.73,
                "clip_start": 2.0,
                "clip_end": 14.0,
                "duration": 12.0,
                "pacing": "fast",
                "caption_style": "sports_hype",
                "crop_strategy": "action",
                "render_style": "sports_hype",
                "hook_options": ["What a finish.", "He scored from there?"],
                "variants": [
                    {
                        "variant_id": str(uuid.uuid4()),
                        "platform": "youtube_shorts",
                        "aspect_ratio": "9:16",
                        "duration_cap": 60,
                        "caption_safe_zone": True,
                        "watermark": True,
                    }
                ],
            }
        ],
        "cost_estimate_cents": 18,
    }
    plan_row = DirectorPlan(
        id=uuid.uuid4(),
        job_id=job.id,
        tenant_id=tenant_a.id,
        model="deterministic-builder/v1",
        prompt_version="v1",
        plan_json=plan_contract,
    )
    db.add(plan_row)
    db.flush()

    render_job = RenderJob(
        id=uuid.uuid4(),
        job_id=job.id,
        tenant_id=tenant_a.id,
        candidate_id=candidate.id,
        pipeline="sports_hype",
        platform="youtube_shorts",
        status="succeeded",
        settings={"crf": 21},
        finished_at=now + timedelta(minutes=4),
        cost_cents=11,
    )
    db.add(render_job)
    db.flush()

    render_output = RenderOutput(
        id=uuid.uuid4(),
        render_job_id=render_job.id,
        tenant_id=tenant_a.id,
        r2_key=f"tenant/{tenant_a.id}/render/{render_job.id}/out.mp4",
        aspect_ratio="9:16",
        duration_s=12.0,
        bytes=1_580_000,
        output_metadata={"renderer": "sports_hype"},
    )
    db.add(render_output)
    db.flush()

    export = ExportArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        render_output_id=render_output.id,
        platform="youtube_shorts",
        export_status="uploaded",
        export_version=1,
        export_hash="a" * 64,
        content_hash="c6440cd1" + "0" * 56,
        content_bytes=1_580_000,
        filename="out.mp4",
        storage_uri=f"r2://aidirector/{render_output.r2_key}",
        artifact_metadata={"renderer": "sports_hype"},
        published_at=now + timedelta(minutes=5),
    )
    db.add(export)
    db.flush()

    experiment = ExperimentGroup(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        experiment_name="hook_v1",
        experiment_version=1,
        hypothesis="curiosity-first hooks outperform spoiler hooks",
    )
    db.add(experiment)
    db.flush()

    fv = PerformanceFeatureSet(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        export_id=export.id,
        experiment_group_id=experiment.id,
        feature_version="v1",
        maturity_state="stable",
        engagement_confidence=0.64,
        normalized_view_rate=0.81,
        normalized_completion_rate=0.74,
        normalized_watch_time=0.68,
        replay_rate=0.12,
        share_rate=0.07,
        engagement_score=0.82,
        evaluated_at=now + timedelta(hours=24),
        derived_metadata={"sample_size": 9420},
    )
    db.add(fv)
    db.flush()

    snapshot = RankingSnapshot(
        id=uuid.uuid4(),
        tenant_id=tenant_a.id,
        candidate_id=candidate.id,
        job_id=job.id,
        source_export_id=export.id,
        base_rank_score=0.394,
        engagement_adjustment=0.096,
        final_rank_score=0.49,
        feature_version="v1",
        feedback_applied=True,
        confidence_threshold=0.30,
        engagement_weight_cap=0.15,
        explanation="Engagement positive (score=0.82), confidence 0.64 above threshold; capped at +0.096.",
        snapshot_metadata={"engagement_score": 0.82, "engagement_confidence": 0.64},
    )
    db.add(snapshot)
    db.flush()

    for ev_type in (
        "upload_created",
        "analysis_started",
        "analysis_completed",
        "ranking_completed",
        "director_plan_created",
        "render_started",
        "render_completed",
        "export_created",
        "engagement_ingested",
        "evaluation_completed",
        "ranking_feedback_applied",
    ):
        db.add(
            UsageEvent(
                id=uuid.uuid4(),
                tenant_id=tenant_a.id,
                upload_id=upload.id,
                job_id=job.id,
                event_type=ev_type,
                quantity=1.0,
                unit="event",
                estimated_cost_cents=None,
                event_metadata={},
            )
        )
    db.commit()

    log("seed complete")

    # --- A: build_job_view returns a JobView -------------------------------
    view = build_job_view(db, tenant=tenant_a, job_id=job.id)
    if view is None:
        log("A: FAIL build_job_view returned None")
        return 5
    if not isinstance(view, JobViewModel):
        log(f"A: FAIL build_job_view returned {type(view).__name__}")
        return 5
    log("A: PASS build_job_view returns JobView")

    # --- B: every collection populated -------------------------------------
    expectations = {
        "scenes": (view.scenes, 2),
        "candidates": (view.candidates, 1),
        "render_jobs": (view.render_jobs, 1),
        "render_outputs": (view.render_outputs, 1),
        "exports": (view.exports, 1),
        "feature_views": (view.feature_views, 1),
        "snapshots": (view.snapshots, 1),
        "usage_events": (view.usage_events, 11),
    }
    for name, (collection, expected) in expectations.items():
        actual = len(collection)
        if actual != expected:
            log(f"B: FAIL {name} expected={expected} actual={actual}")
            return 6
        log(f"B: PASS {name}={actual}")

    # --- C: feature_views is the 12-field projection -----------------------
    fview = view.feature_views[0]
    fview_fields = set(fview.model_dump().keys())
    expected_fview_fields = {
        "export_id",
        "tenant_id",
        "feature_version",
        "maturity_state",
        "engagement_confidence",
        "normalized_view_rate",
        "normalized_completion_rate",
        "normalized_watch_time",
        "replay_rate",
        "share_rate",
        "engagement_score",
        "experiment_group_id",
    }
    if fview_fields != expected_fview_fields:
        log(
            f"C: FAIL feature_view fields drift "
            f"missing={expected_fview_fields - fview_fields} "
            f"extra={fview_fields - expected_fview_fields}"
        )
        return 7
    log(f"C: PASS feature_view exposes exactly {len(fview_fields)} fields, no raw engagement leak")

    # --- D: ranking snapshot preserves Phase 8 fields ----------------------
    snap = view.snapshots[0]
    if abs(snap.base_rank_score - 0.394) > 1e-9:
        log(f"D: FAIL base_rank_score={snap.base_rank_score}")
        return 8
    if abs(snap.engagement_adjustment - 0.096) > 1e-9:
        log(f"D: FAIL engagement_adjustment={snap.engagement_adjustment}")
        return 8
    if abs(snap.final_rank_score - 0.49) > 1e-9:
        log(f"D: FAIL final_rank_score={snap.final_rank_score}")
        return 8
    if abs(snap.confidence_threshold - 0.30) > 1e-9:
        log(f"D: FAIL confidence_threshold={snap.confidence_threshold}")
        return 8
    if abs(snap.engagement_weight_cap - 0.15) > 1e-9:
        log(f"D: FAIL engagement_weight_cap={snap.engagement_weight_cap}")
        return 8
    if not snap.feedback_applied:
        log("D: FAIL feedback_applied is False")
        return 8
    log(
        f"D: PASS snapshot base={snap.base_rank_score} adj={snap.engagement_adjustment} "
        f"final={snap.final_rank_score} cap={snap.engagement_weight_cap} threshold={snap.confidence_threshold}"
    )

    # --- E: director_plan deserialised through the contract ----------------
    if view.director_plan is None:
        log("E: FAIL director_plan is None")
        return 9
    if view.director_plan.version != DIRECTOR_PLAN_VERSION:
        log(f"E: FAIL director_plan.version={view.director_plan.version}")
        return 9
    if len(view.director_plan.selected_candidates) != 1:
        log(f"E: FAIL selected_candidates count={len(view.director_plan.selected_candidates)}")
        return 9
    log(
        f"E: PASS director_plan version={view.director_plan.version} "
        f"selected={len(view.director_plan.selected_candidates)} "
        f"variants={sum(len(c.variants) for c in view.director_plan.selected_candidates)}"
    )

    # --- F: tenant isolation -----------------------------------------------
    foreign = build_job_view(db, tenant=tenant_b, job_id=job.id)
    if foreign is not None:
        log("F: FAIL tenant_b can see tenant_a job")
        return 10
    log("F: PASS tenant_b sees nothing for tenant_a job")

    # --- G: events counts match collections --------------------------------
    events = build_job_events(db, tenant=tenant_a, job_id=job.id)
    if events is None:
        log("G: FAIL build_job_events returned None")
        return 11
    paired = {
        "scenes": (events.counts["scenes"], len(view.scenes)),
        "candidates": (events.counts["candidates"], len(view.candidates)),
        "render_jobs": (events.counts["render_jobs"], len(view.render_jobs)),
        "render_outputs": (events.counts["render_outputs"], len(view.render_outputs)),
        "exports": (events.counts["exports"], len(view.exports)),
        "feature_views": (events.counts["feature_views"], len(view.feature_views)),
        "snapshots": (events.counts["snapshots"], len(view.snapshots)),
        "usage_events": (events.counts["usage_events"], len(view.usage_events)),
    }
    for name, (counted, listed) in paired.items():
        if counted != listed:
            log(f"G: FAIL {name} count={counted} but view returns {listed}")
            return 11
    if events.revision != len(view.usage_events):
        log(f"G: FAIL revision={events.revision} usage_events={len(view.usage_events)}")
        return 11
    if events.status != job.status:
        log(f"G: FAIL events.status={events.status} job.status={job.status}")
        return 11
    log(
        f"G: PASS events.revision={events.revision} "
        f"status={events.status} last_event={events.last_event_type}"
    )

    # --- H: serialises to JSON cleanly -------------------------------------
    payload = view.model_dump(mode="json")
    blob = json.dumps(payload)
    parsed = json.loads(blob)
    expected_top_keys = {
        "job",
        "upload",
        "scenes",
        "candidates",
        "director_plan",
        "render_jobs",
        "render_outputs",
        "exports",
        "feature_views",
        "snapshots",
        "usage_events",
    }
    if set(parsed.keys()) != expected_top_keys:
        log(
            f"H: FAIL JobView top keys drift "
            f"missing={expected_top_keys - set(parsed.keys())} "
            f"extra={set(parsed.keys()) - expected_top_keys}"
        )
        return 12
    log(f"H: PASS JobView JSON {len(blob)} bytes, {len(parsed)} top-level keys")

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
