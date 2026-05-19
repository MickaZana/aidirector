"""Phase 5 integration probe — RenderManifest + real FFmpeg execution.

Proves the analyze → rank → direct → render chain:

  upload → analysis job → scenes persisted (Phase 2) → candidates persisted
   (Phase 3) → DirectorPlan (Phase 4) → RenderManifest objects → renderer
   compatibility validation → FFmpeg execution → RenderJob + RenderOutput
   persistence → usage_events (render_started, render_completed)

Five sub-tests inside one probe:

  A) Manifest building: 6 manifests built from 2 candidates × 3 platforms.
     Each manifest validates via Pydantic; each is renderer-compatible.

  B) Renderer compatibility rejection: a manually-constructed manifest with
     documentary renderer + 9:16 aspect (registry says 16:9/1:1 only) is
     rejected with a clear reason. Empirical proof the registry gate works.

  C) Dry-run command construction: deterministic FFmpeg argv list for one
     manifest. Same manifest → same command bytes, on every run.

  D) Real FFmpeg execution: render one variant to local disk against a
     generated test-source. Output file exists with non-zero bytes.

  E) Persistence: RenderJob INSERT + INSERT RenderOutput + RENDER_STARTED
     + RENDER_COMPLETED usage events. FK chain intact.

Writes a report to _probe_phase5_loop.out.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase5_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"
FIXTURE_DIR = Path(__file__).parent / "_probe_phase5_fixtures"
SOURCE_PATH = FIXTURE_DIR / "source_30s.mp4"
RENDER_OUTPUT_DIR = FIXTURE_DIR / "renders"


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
    """Generate a 30-second 320x240 test-pattern source via ffmpeg lavfi."""
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_PATH.exists() and SOURCE_PATH.stat().st_size > 0:
        return str(SOURCE_PATH)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not on PATH; cannot generate fixture source")
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

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    _silent(lambda: command.upgrade(cfg, "head"))
    log("alembic upgrade head: OK")

    source_uri = _ensure_fixture_source()
    log(f"fixture source: {source_uri} ({Path(source_uri).stat().st_size} bytes)")

    # --- Phase 2 / 3 / 4 chain to get a DirectorPlan ----------------------
    from api.services.intel.scene_analysis_adapter import analyze_video
    from api.services.intel.clip_ranking_adapter import rank_clip_candidates
    from api.services.intel.capability_registry import SceneRecord
    from api.services.scene_persistence import persist_scene_analysis
    from api.services.clip_candidate_persistence import persist_clip_candidates
    from api.services.director_plan_builder import build_director_plan
    from api.services.director_plan_persistence import persist_director_plan
    from api.services.usage_events import emit_usage_event

    fixture_reads = [
        {"t":  5.0, "raw_text": "0  -  0    00:30", "ocr_confidence": 0.85},
        {"t":  8.0, "raw_text": "0  -  0    01:00", "ocr_confidence": 0.85},
        {"t": 12.0, "raw_text": "0  -  0    01:30", "ocr_confidence": 0.85},
        {"t": 16.0, "raw_text": "1  -  0    01:35", "ocr_confidence": 0.86},
        {"t": 20.0, "raw_text": "1  -  0    01:40", "ocr_confidence": 0.86},
        {"t": 22.0, "raw_text": "1  -  0    02:00", "ocr_confidence": 0.86},
        {"t": 26.0, "raw_text": "1  -  0    02:30", "ocr_confidence": 0.87},
    ]
    # Only one confirmed change for Phase 5; render time scales with manifests.

    analysis = analyze_video(
        upload_id="probe-upload-phase5",
        source_uri="fixture://memory",
        fixture_reads=fixture_reads,
    )
    log(f"analyzer.scene_count={len(analysis.scenes)}")
    if len(analysis.scenes) < 1:
        log("FAIL: analyzer returned 0 scenes")
        return 2

    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import Session

    from api.models import (
        Job, JobStatus, RenderJob, RenderJobStatus, RenderOutput,
        Tenant, Upload, UploadStatus, UsageEvent, UsageEventType, User,
    )
    from api.schemas.director_plan import DirectorPlan
    from api.schemas.render_manifest import RenderManifest
    from api.services.intel.renderer_registry import (
        CompatibilityResult, RENDERERS, validate_manifest,
    )
    from api.services.render_manifest_builder import build_manifests
    from api.services.intel.render_plan_adapter import render_clip
    from api.services.render_output_persistence import (
        complete_render_job, start_render_job,
    )

    log(f"registry.renderers={sorted(RENDERERS.keys())}")

    engine = create_engine(os.environ["DATABASE_URL"])
    PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels"]

    with Session(engine) as db:
        tenant = Tenant(slug="phase5_probe", name="Phase 5 Probe", plan="creator")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            clerk_user_id="user_probe5_clerk",
            email="probe5@aidirector.app",
            role="admin",
        )
        db.add(user)
        db.flush()
        upload = Upload(
            tenant_id=tenant.id, user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe5/match.mp4",
            filename="match.mp4", bytes=Path(source_uri).stat().st_size,
            duration_s=30.0, sport="football",
            status=UploadStatus.READY.value,
            upload_metadata={"content_type": "video/mp4", "source_uri": source_uri},
        )
        db.add(upload)
        db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id,
            event_type=UsageEventType.UPLOAD_CREATED, unit="upload",
            metadata={"size_bytes": upload.bytes},
        )

        job = Job(
            tenant_id=tenant.id, upload_id=upload.id, intent="analyze",
            status=JobStatus.RUNNING.value, cost_budget_cents=30,
        )
        db.add(job)
        db.flush()
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
            upload_id=str(upload.id),
            job_id=str(job.id),
            candidates=candidate_rows,
            platform_targets=PLATFORMS,
        )
        persist_director_plan(db, job=job, plan=plan)
        log(
            f"director_plan: candidates={len(plan.selected_candidates)} "
            f"variants={sum(len(c.variants) for c in plan.selected_candidates)}"
        )

        # --- sub-test A: manifest building -------------------------------
        result = build_manifests(
            plan=plan, source_uri=source_uri,
            tenant_id=str(tenant.id), tenant_slug=tenant.slug,
        )
        log(f"A.manifests_built={len(result.manifests)}")
        log(f"A.unrenderable={len(result.unrenderable)}")
        for m in result.manifests:
            log(
                f"A.manifest: rj={m.render_job_id[:8]} cand={m.candidate_id[:8]} "
                f"platform={m.platform} aspect={m.aspect_ratio} "
                f"{m.output_width}x{m.output_height}@{m.fps}fps "
                f"renderer={m.renderer} caption={m.caption_mode} "
                f"watermark={m.watermark} normalize_audio={m.normalize_audio} "
                f"crf={m.crf} bitrate_kbps={m.bitrate_kbps}"
            )
        expected_manifests = len(plan.selected_candidates) * len(PLATFORMS)
        if len(result.manifests) != expected_manifests:
            log(f"FAIL.A: expected {expected_manifests} manifests, got {len(result.manifests)}")
            return 3
        for m in result.manifests:
            compat = validate_manifest(m)
            if not compat.compatible:
                log(f"FAIL.A: manifest validation failed: {compat.reasons}")
                return 4

        # --- sub-test B: compatibility rejection of bad manifest --------
        bad_manifest = result.manifests[0].model_copy(
            update={
                "renderer": "documentary",
                "render_style": "documentary",
                "aspect_ratio": "9:16",  # docs renderer only supports 16:9, 1:1
                "caption_mode": "documentary",
                "crop_mode": "center",
            }
        )
        bad_compat = validate_manifest(bad_manifest)
        log(f"B.bad_manifest.compatible={bad_compat.compatible}")
        log(f"B.bad_manifest.reasons={list(bad_compat.reasons)}")
        if bad_compat.compatible:
            log("FAIL.B: bad documentary+9:16 manifest passed validation")
            return 5
        if not any("aspect" in r for r in bad_compat.reasons):
            log("FAIL.B: rejection reason did not mention aspect ratio")
            return 6

        # --- sub-test C: dry-run command construction -------------------
        dry_result_a = render_clip(
            result.manifests[0], output_dir=RENDER_OUTPUT_DIR, dry_run=True
        )
        dry_result_b = render_clip(
            result.manifests[0], output_dir=RENDER_OUTPUT_DIR, dry_run=True
        )
        log(f"C.dry_run.status={dry_result_a.status}")
        log(f"C.dry_run.command_len={len(dry_result_a.command)}")
        log(f"C.dry_run.argv0={Path(dry_result_a.command[0]).name}")
        log(f"C.dry_run.deterministic={dry_result_a.command == dry_result_b.command}")
        if dry_result_a.command != dry_result_b.command:
            log("FAIL.C: dry-run produced non-deterministic commands across runs")
            return 7
        if "-vf" not in dry_result_a.command:
            log("FAIL.C: command missing -vf flag")
            return 8

        # --- sub-test D: real FFmpeg execution for one manifest ---------
        target = result.manifests[0]
        rj_row = start_render_job(db, job=job, manifest=target)
        db.flush()
        exec_result = render_clip(target, output_dir=RENDER_OUTPUT_DIR)
        log(f"D.exec.status={exec_result.status}")
        log(f"D.exec.output_path={exec_result.output_path}")
        log(f"D.exec.bytes={exec_result.bytes}")
        log(f"D.exec.elapsed_seconds={exec_result.elapsed_seconds:.2f}")
        if exec_result.status != "succeeded":
            log(f"FAIL.D: render did not succeed: error={exec_result.error}")
            log(f"FAIL.D: stderr_tail={exec_result.stderr_tail}")
            return 9
        if not exec_result.output_path or not Path(exec_result.output_path).exists():
            log("FAIL.D: output file missing after render")
            return 10
        if not exec_result.bytes or exec_result.bytes <= 0:
            log(f"FAIL.D: output file empty (bytes={exec_result.bytes})")
            return 11

        # --- sub-test E: persistence --------------------------------------
        complete_render_job(
            db, job=job, render_job=rj_row, manifest=target, result=exec_result
        )
        db.commit()

    with Session(engine) as db:
        rj_count = db.execute(select(func.count()).select_from(RenderJob)).scalar()
        ro_count = db.execute(select(func.count()).select_from(RenderOutput)).scalar()
        log(f"db.render_jobs={rj_count}")
        log(f"db.render_outputs={ro_count}")
        if rj_count != 1 or ro_count != 1:
            log(f"FAIL.E: expected 1 RenderJob + 1 RenderOutput, got {rj_count}+{ro_count}")
            return 12

        rj = db.execute(select(RenderJob)).scalar_one()
        log(f"db.rj.status={rj.status} pipeline={rj.pipeline} platform={rj.platform}")
        log(f"db.rj.cost_cents={rj.cost_cents} finished_at={rj.finished_at is not None}")
        if rj.status != RenderJobStatus.SUCCEEDED.value:
            log(f"FAIL.E: RenderJob status not SUCCEEDED: {rj.status}")
            return 13

        ro = db.execute(select(RenderOutput)).scalar_one()
        log(f"db.ro.aspect_ratio={ro.aspect_ratio} bytes={ro.bytes} duration_s={ro.duration_s}")
        log(f"db.ro.r2_key={ro.r2_key}")
        log(f"db.ro.output_metadata={json.dumps(ro.output_metadata)}")

        usage = db.execute(select(UsageEvent)).scalars().all()
        events = sorted({(u.event_type, u.unit) for u in usage})
        log(f"db.usage_events={json.dumps(events)}")
        if not any(e[0] == "render_started" for e in events):
            log("FAIL.E: render_started missing")
            return 14
        if not any(e[0] == "render_completed" for e in events):
            log("FAIL.E: render_completed missing")
            return 15

    log("sub-tests A/B/C/D/E: OK")
    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
