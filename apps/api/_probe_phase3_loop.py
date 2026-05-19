"""Phase 3 integration probe — real OmegaClips clip ranking.

Proves the analyze → rank chain:

  upload → analysis job → scenes persisted (Phase 2 path) → ranker
    → clip_candidates persisted → usage_events written
        (candidate_created N×, ranking_completed)

Real OmegaClips capabilities exercised:
  - football_pipeline.config.PipelineConfig
  - football_pipeline.window_ranking.rank_goal_candidate_windows_for_intent
    (capability map IDs #11 best moments, #21 quality, #23 confidence — all A)
  - football_pipeline.scoreboard.build_score_change_context (called by ranker)

Writes a report to _probe_phase3_loop.out.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase3_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"


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


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    log("step: start")
    if PROBE_DB.exists():
        PROBE_DB.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    _silent(lambda: command.upgrade(cfg, "head"))
    log("alembic upgrade head: OK")

    # --- analyzer first (re-use Phase 2 fixture) -------------------------
    from api.services.intel.scene_analysis_adapter import analyze_video

    fixture = [
        {"t":  5.0, "raw_text": "0  -  0    00:30", "ocr_confidence": 0.85},
        {"t":  8.0, "raw_text": "0  -  0    01:00", "ocr_confidence": 0.85},
        {"t": 12.0, "raw_text": "0  -  0    01:30", "ocr_confidence": 0.85},
        {"t": 16.0, "raw_text": "1  -  0    01:35", "ocr_confidence": 0.86},
        {"t": 20.0, "raw_text": "1  -  0    01:40", "ocr_confidence": 0.86},
        {"t": 22.0, "raw_text": "1  -  0    02:00", "ocr_confidence": 0.86},
        {"t": 26.0, "raw_text": "1  -  0    02:30", "ocr_confidence": 0.87},
        {"t": 32.0, "raw_text": "1  -  0    03:00", "ocr_confidence": 0.86},
        {"t": 38.0, "raw_text": "1  -  0    03:30", "ocr_confidence": 0.86},
        {"t": 44.0, "raw_text": "1  -  1    04:00", "ocr_confidence": 0.84},
        {"t": 48.0, "raw_text": "1  -  1    04:30", "ocr_confidence": 0.84},
        {"t": 50.0, "raw_text": "1  -  1    04:45", "ocr_confidence": 0.85},
        {"t": 54.0, "raw_text": "1  -  1    05:00", "ocr_confidence": 0.85},
    ]
    analysis = analyze_video(
        upload_id="probe-upload-phase3",
        source_uri="fixture://memory",
        fixture_reads=fixture,
    )
    log(f"analyzer.scene_count={len(analysis.scenes)}")
    if len(analysis.scenes) < 2:
        log("FAIL: analyzer did not return ≥2 scenes; phase 2 fixture broken?")
        return 4

    # --- build DB rows + run the ranker via adapter -----------------------
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from api.models import (
        ClipCandidate,
        Job,
        JobStatus,
        Scene,
        Tenant,
        Upload,
        UploadStatus,
        UsageEvent,
        UsageEventType,
        User,
    )
    from api.services.clip_candidate_persistence import persist_clip_candidates
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.scene_persistence import persist_scene_analysis
    from api.services.usage_events import emit_usage_event

    engine = create_engine(os.environ["DATABASE_URL"])

    with Session(engine) as db:
        tenant = Tenant(slug="phase3_probe", name="Phase 3 Probe", plan="creator")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            clerk_user_id="user_probe3_clerk",
            email="probe3@aidirector.app",
            role="admin",
        )
        db.add(user)
        db.flush()
        upload = Upload(
            tenant_id=tenant.id,
            user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe3/match.mp4",
            filename="match.mp4",
            bytes=104857600,
            duration_s=60.0,
            sport="football",
            status=UploadStatus.READY.value,
            upload_metadata={"content_type": "video/mp4"},
        )
        db.add(upload)
        db.flush()
        emit_usage_event(
            db,
            tenant_id=tenant.id,
            upload_id=upload.id,
            event_type=UsageEventType.UPLOAD_CREATED,
            unit="upload",
            metadata={"size_bytes": upload.bytes},
        )

        job = Job(
            tenant_id=tenant.id,
            upload_id=upload.id,
            intent="analyze",
            status=JobStatus.RUNNING.value,
            cost_budget_cents=30,
        )
        db.add(job)
        db.flush()
        emit_usage_event(
            db,
            tenant_id=tenant.id,
            upload_id=upload.id,
            job_id=job.id,
            event_type=UsageEventType.ANALYSIS_STARTED,
            unit="job",
            metadata={"intent": job.intent},
        )
        scene_rows = persist_scene_analysis(db, job=job, result=analysis)
        log(f"persisted_scene_rows={len(scene_rows)}")

        # Ranking starts here. Job is already SUCCEEDED from analysis; we
        # emit RANKING_STARTED to mark the second phase of work.
        emit_usage_event(
            db,
            tenant_id=tenant.id,
            upload_id=upload.id,
            job_id=job.id,
            event_type=UsageEventType.RANKING_STARTED,
            unit="job",
            metadata={"scene_count": len(scene_rows)},
        )

        # --- Real OmegaClips ranking call ---------------------------------
        ranked = rank_clip_candidates(
            upload_id=str(upload.id),
            scenes=[
                # Convert Scene rows back to SceneRecord shape for the adapter.
                # In the production worker this round-trips via JSON.
                __import__(
                    "api.services.intel.capability_registry",
                    fromlist=["SceneRecord"],
                ).SceneRecord(
                    t_start=s.t_start,
                    t_end=s.t_end,
                    kind=s.kind,
                    arc_position=s.arc_position,
                    intensity=s.intensity,
                    importance=s.importance,
                    signals=s.signals,
                )
                for s in scene_rows
            ],
        )
        log(f"ranked.candidate_count={len(ranked.candidates)}")
        for i, c in enumerate(ranked.candidates):
            log(
                f"candidate[{i}]: t_start={c.t_start} t_end={c.t_end} "
                f"confidence={c.confidence_score} quality={c.quality_score} "
                f"platform={c.platform_score}"
            )
            log(f"  rationale={c.rationale}")
            log(
                f"  scores.rank={c.scores.get('rank')} "
                f"rank_score={c.scores.get('rank_score')} "
                f"intent={c.scores.get('ranking_intent')} "
                f"engine={c.scores.get('ranking_engine')}"
            )

        rows = persist_clip_candidates(
            db, job=job, scenes_in_order=scene_rows, ranked=ranked
        )
        log(f"persisted_candidate_rows={len(rows)}")
        db.commit()

    # --- DB verification --------------------------------------------------
    with Session(engine) as db:
        candidate_count = db.execute(select(func.count()).select_from(ClipCandidate)).scalar()
        log(f"db.candidates_count={candidate_count}")

        for c in db.execute(select(ClipCandidate)).scalars().all():
            log(
                f"  db candidate: scene_id={c.scene_id} "
                f"t_start={c.t_start} t_end={c.t_end} "
                f"confidence={c.confidence_score} quality={c.quality_score} "
                f"platform={c.platform_score}"
            )
            log(f"    rationale={c.rationale}")
            log(f"    scores.rank={c.scores.get('rank')} rank_score={c.scores.get('rank_score')}")

        # FK integrity: every candidate scene_id must point to a real scene
        for c in db.execute(select(ClipCandidate)).scalars().all():
            if c.scene_id is None:
                log("FAIL: candidate.scene_id is NULL — should link to a Scene row")
                return 5
            scene = db.execute(select(Scene).where(Scene.id == c.scene_id)).scalar_one_or_none()
            if scene is None:
                log(f"FAIL: candidate.scene_id {c.scene_id} has no matching Scene row")
                return 6
            if c.tenant_id != scene.tenant_id:
                log("FAIL: candidate.tenant_id != scene.tenant_id")
                return 7

        usage_rows = db.execute(select(UsageEvent)).scalars().all()
        events = sorted({(u.event_type, u.unit, float(u.quantity)) for u in usage_rows})
        log(f"db.usage_events={json.dumps(events)}")
        if not any(e[0] == "candidate_created" for e in events):
            log("FAIL: candidate_created usage event missing")
            return 8
        if not any(e[0] == "ranking_completed" for e in events):
            log("FAIL: ranking_completed usage event missing")
            return 9
        if not any(e[0] == "ranking_started" for e in events):
            log("FAIL: ranking_started usage event missing")
            return 10

        candidate_created_rows = [u for u in usage_rows if u.event_type == "candidate_created"]
        if len(candidate_created_rows) != candidate_count:
            log(
                f"FAIL: candidate_created event count {len(candidate_created_rows)} "
                f"!= persisted candidate count {candidate_count}"
            )
            return 11

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
