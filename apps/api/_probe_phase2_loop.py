"""Phase 2 integration probe.

Proves the upload → analysis-job → real-OmegaClips-adapter → scenes-persisted
→ usage_events chain without needing Modal credentials or a real video.

Real OmegaClips capabilities exercised:
  - football_pipeline.config.PipelineConfig (instantiated)
  - football_pipeline.scoreboard.normalize_ocr_text (called per fixture read)
  - football_pipeline.scoreboard.parse_score (called per fixture read)
  - football_pipeline.scoreboard.ScoreboardChangeTracker (full lifecycle)
  - football_pipeline.models.ScoreboardState (constructed)

Writes a report to _probe_phase2_loop.out.
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase2_loop.out"
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
    log("step: sys.path set")

    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        log("alembic import failed:")
        log(traceback.format_exc())
        return 2
    log("step: alembic imported")

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    log("step: alembic config built")
    _silent(lambda: command.upgrade(cfg, "head"))
    log("alembic upgrade head: OK")

    # Real OmegaClips import — proves the adapter boundary works in this env
    try:
        from api.services.intel.scene_analysis_adapter import analyze_video
    except Exception:
        log("ADAPTER IMPORT FAILED:")
        log(traceback.format_exc())
        return 3

    # Synthetic OCR fixture — simulates 0-0 → 1-0 → 1-1 score progression
    # across the first 60s of "video time". Each read includes raw text that
    # OmegaClips' parse_score will actually need to extract scores from.
    # Hold-window default is 4.0s + 2 consensus reads, so we provide
    # enough confirming reads at each new score to trigger detection.
    fixture = [
        # Pre-match: 0-0 stable baseline
        {"t":  5.0, "raw_text": "0  -  0    00:30",  "ocr_confidence": 0.85},
        {"t":  8.0, "raw_text": "0  -  0    01:00",  "ocr_confidence": 0.85},
        {"t": 12.0, "raw_text": "0  -  0    01:30",  "ocr_confidence": 0.85},
        # Goal 1 → score becomes 1-0
        {"t": 16.0, "raw_text": "1  -  0    01:35",  "ocr_confidence": 0.86},
        {"t": 20.0, "raw_text": "1  -  0    01:40",  "ocr_confidence": 0.86},
        {"t": 22.0, "raw_text": "1  -  0    02:00",  "ocr_confidence": 0.86},
        {"t": 26.0, "raw_text": "1  -  0    02:30",  "ocr_confidence": 0.87},
        # Stable 1-0
        {"t": 32.0, "raw_text": "1  -  0    03:00",  "ocr_confidence": 0.86},
        {"t": 38.0, "raw_text": "1  -  0    03:30",  "ocr_confidence": 0.86},
        # Goal 2 → 1-1 equaliser
        {"t": 44.0, "raw_text": "1  -  1    04:00",  "ocr_confidence": 0.84},
        {"t": 48.0, "raw_text": "1  -  1    04:30",  "ocr_confidence": 0.84},
        {"t": 50.0, "raw_text": "1  -  1    04:45",  "ocr_confidence": 0.85},
        {"t": 54.0, "raw_text": "1  -  1    05:00",  "ocr_confidence": 0.85},
    ]

    result = analyze_video(
        upload_id="probe-upload-0001",
        source_uri="fixture://memory",
        fixture_reads=fixture,
    )
    log(f"scene_count={len(result.scenes)}")
    log(f"intel_submodule_sha={result.intel_submodule_sha}")
    log(f"raw_metrics={json.dumps(result.raw_metrics)}")
    for i, scene in enumerate(result.scenes):
        log(f"scene[{i}]: kind={scene.kind} t_start={scene.t_start} "
            f"t_end={scene.t_end} intensity={scene.intensity}")
        log(f"  signals.scoreboard_delta={json.dumps(scene.signals.get('scoreboard_delta'))}")
        log(f"  signals.confirmed_via={scene.signals.get('confirmed_via')}")
        log(f"  signals.supporting_reads={scene.signals.get('supporting_reads')}")

    if len(result.scenes) == 0:
        log("FAIL: ScoreboardChangeTracker produced zero scenes — fixture should yield ≥2")
        return 4

    # Persist via the full DB chain — same code path the worker will use.
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from api.models import Job, JobStatus, Scene, Tenant, Upload, UploadStatus, User, UsageEvent, UsageEventType
    from api.services.scene_persistence import persist_scene_analysis
    from api.services.usage_events import emit_usage_event

    engine = create_engine(os.environ["DATABASE_URL"])

    with Session(engine) as db:
        tenant = Tenant(slug="phase2_probe", name="Phase 2 Probe", plan="creator")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            clerk_user_id="user_probe_clerk",
            email="probe@aidirector.app",
            role="admin",
        )
        db.add(user)
        db.flush()
        upload = Upload(
            tenant_id=tenant.id,
            user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe2/match.mp4",
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
            intel_submodule_sha=None,
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

        # The adapter has already produced `result`. The persistence call is
        # what writes scenes + flips job to succeeded + emits ANALYSIS_COMPLETED.
        rows = persist_scene_analysis(db, job=job, result=result)
        db.commit()

        log(f"persisted_scene_rows={len(rows)}")

    # Verify everything landed in DB
    with Session(engine) as db:
        scene_count = db.execute(select(func.count()).select_from(Scene)).scalar()
        log(f"db.scenes_count={scene_count}")

        for s in db.execute(select(Scene)).scalars().all():
            log(f"  db scene: kind={s.kind} t_start={s.t_start} "
                f"signals_delta={s.signals.get('scoreboard_delta')}")

        usage_rows = db.execute(select(UsageEvent)).scalars().all()
        events = sorted({(u.event_type, u.unit, float(u.quantity)) for u in usage_rows})
        log(f"db.usage_events={json.dumps(events)}")

        # Job must be SUCCEEDED and have submodule sha stamped
        job_row = db.execute(select(Job)).scalar_one()
        log(f"db.job.status={job_row.status}")
        log(f"db.job.intel_submodule_sha={job_row.intel_submodule_sha}")

        if job_row.status != JobStatus.SUCCEEDED.value:
            log("FAIL: job not marked SUCCEEDED after analysis")
            return 5
        if scene_count != len(result.scenes):
            log(f"FAIL: persisted {scene_count} but adapter returned {len(result.scenes)}")
            return 6
        if not any(e[0] == "analysis_started" for e in events):
            log("FAIL: analysis_started usage event missing")
            return 7
        if not any(e[0] == "analysis_completed" for e in events):
            log("FAIL: analysis_completed usage event missing")
            return 8

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
