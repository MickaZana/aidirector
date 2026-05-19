"""Phase 6 integration probe — ExportArtifact canonical identity layer.

Proves the analyze → rank → direct → render → export chain:

  RenderOutput (Phase 5)
   → export_artifact_builder.build_export_artifact (deterministic identity)
   → r2.put_local_file (local-mode storage transport)
   → export_persistence.persist_export_artifact (row + EXPORT_CREATED)
   → telemetry-ready ExportArtifact identity

Sub-tests inside one probe:

  A) Schema: exports table exists with required columns + indexes.

  B) Hash determinism: build_export_artifact called twice on the same
     file produces identical content_hash and identical filename.
     (export_id is a new UUID each time — that's correct; identity
     across re-runs is via export_hash + content_hash.)

  C) Lineage: ExportArtifact.render_output_id == RenderOutput.id; tenant
     scoping intact; storage_uri parses cleanly.

  D) Real end-to-end: 1 RenderOutput → 1 ExportArtifact persisted →
     storage file exists at the parsed local path → row carries non-empty
     content_hash, content_bytes matching file size.

  E) Idempotency: bumping export_version changes export_hash but keeps
     content_hash stable (proves the two-hash design works).

  F) Usage event: EXPORT_CREATED present with the expected metadata keys.

Writes a report to _probe_phase6_loop.out.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import traceback
import uuid
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase6_loop.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"
FIXTURE_DIR = Path(__file__).parent / "_probe_phase6_fixtures"
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
    log(f"fixture source: {source_uri}")

    # --- sub-test A: schema -------------------------------------------------
    from sqlalchemy import create_engine, func, inspect, select
    from sqlalchemy.orm import Session

    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    log(f"A.tables={tables}")
    if "exports" not in tables:
        log("FAIL.A: exports table not created")
        return 2

    expected_cols = {
        "id", "tenant_id", "render_output_id", "platform", "export_status",
        "export_version", "export_hash", "content_hash", "content_bytes",
        "filename", "storage_uri", "artifact_metadata", "published_at",
        "created_at", "updated_at",
    }
    actual_cols = {c["name"] for c in inspector.get_columns("exports")}
    missing = expected_cols - actual_cols
    log(f"A.exports.cols={sorted(actual_cols)}")
    if missing:
        log(f"FAIL.A: missing columns {sorted(missing)}")
        return 3

    expected_idx = {
        "ix_exports_tenant_id_platform",
        "ix_exports_tenant_id_created_at",
        "ix_exports_render_output_id",
        "ix_exports_export_hash",
        "ix_exports_content_hash",
        "ix_exports_export_status",
    }
    actual_idx = {i["name"] for i in inspector.get_indexes("exports")}
    log(f"A.exports.indexes={sorted(actual_idx)}")
    missing_idx = expected_idx - actual_idx
    if missing_idx:
        log(f"FAIL.A: missing indexes {sorted(missing_idx)}")
        return 4

    # --- Phase 2-5 chain to get a real RenderOutput -----------------------
    from api.models import (
        Job, JobStatus, RenderJob, RenderOutput,
        Tenant, Upload, UploadStatus, User, UsageEvent, UsageEventType,
        ExportArtifact, ExportArtifactStatus,
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
    from api.services.usage_events import emit_usage_event
    from api.services.export_artifact_builder import build_export_artifact
    from api.services.export_persistence import persist_export_artifact
    from api.services.r2 import (
        build_storage_uri, export_key, is_r2_configured,
        parse_storage_uri, put_local_file,
    )

    log(f"r2.is_r2_configured={is_r2_configured()}")
    log(f"r2.local_mirror={LOCAL_STORAGE_MIRROR}")

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
        upload_id="probe-upload-phase6",
        source_uri="fixture://memory",
        fixture_reads=fixture_reads,
    )
    log(f"chain.analyzer.scene_count={len(analysis.scenes)}")

    PLATFORMS = ["youtube_shorts", "tiktok", "instagram_reels"]
    with Session(engine) as db:
        tenant = Tenant(slug="phase6_probe", name="Phase 6 Probe", plan="creator")
        db.add(tenant); db.flush()
        user = User(
            tenant_id=tenant.id, clerk_user_id="user_probe6",
            email="probe6@aidirector.app", role="admin",
        )
        db.add(user); db.flush()
        upload = Upload(
            tenant_id=tenant.id, user_id=user.id,
            r2_key=f"tenant/{tenant.id}/upload/probe6/match.mp4",
            filename="match.mp4", bytes=Path(source_uri).stat().st_size,
            duration_s=30.0, sport="football",
            status=UploadStatus.READY.value,
            upload_metadata={"source_uri": source_uri},
        )
        db.add(upload); db.flush()
        emit_usage_event(
            db, tenant_id=tenant.id, upload_id=upload.id,
            event_type=UsageEventType.UPLOAD_CREATED, unit="upload",
            metadata={"size_bytes": upload.bytes},
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
        target_manifest = manifest_result.manifests[0]
        log(f"chain.render.manifest: platform={target_manifest.platform}")

        rj_row = start_render_job(db, job=job, manifest=target_manifest)
        db.flush()
        exec_result = render_clip(target_manifest, output_dir=RENDER_OUTPUT_DIR)
        if exec_result.status != "succeeded":
            log(f"FAIL.chain: render failed: {exec_result.error}")
            return 5
        ro_row = complete_render_job(
            db, job=job, render_job=rj_row,
            manifest=target_manifest, result=exec_result,
        )
        log(f"chain.render_output_id={ro_row.id}")
        log(f"chain.local_render_path={exec_result.output_path}")
        db.commit()

        # --- sub-test B: hash determinism --------------------------------
        cand_uuid = uuid.UUID(target_manifest.candidate_id)
        inputs1 = build_export_artifact(
            render_output=ro_row, tenant_slug=tenant.slug,
            candidate_id=cand_uuid, platform=target_manifest.platform,
            local_source_path=Path(exec_result.output_path),
            export_version=1,
        )
        inputs2 = build_export_artifact(
            render_output=ro_row, tenant_slug=tenant.slug,
            candidate_id=cand_uuid, platform=target_manifest.platform,
            local_source_path=Path(exec_result.output_path),
            export_version=1,
        )
        log(f"B.content_hash_a={inputs1.content_hash}")
        log(f"B.content_hash_b={inputs2.content_hash}")
        log(f"B.filename_a={inputs1.filename}")
        log(f"B.filename_b={inputs2.filename}")
        log(f"B.export_hash_a={inputs1.export_hash}")
        log(f"B.export_hash_b={inputs2.export_hash}")
        if inputs1.content_hash != inputs2.content_hash:
            log("FAIL.B: content_hash not deterministic")
            return 6
        if inputs1.filename != inputs2.filename:
            log("FAIL.B: filename not deterministic")
            return 7
        if inputs1.export_hash != inputs2.export_hash:
            log("FAIL.B: export_hash not deterministic for same identity tuple")
            return 8
        if inputs1.export_id == inputs2.export_id:
            log("FAIL.B: export_id reused — should be a fresh UUID per build")
            return 9
        if len(inputs1.content_hash) != 64:
            log(f"FAIL.B: content_hash not 64-char SHA256 hex: {inputs1.content_hash}")
            return 10

        # --- sub-test C: storage URI + transport + lineage ---------------
        key = export_key(str(tenant.id), str(inputs1.export_id), inputs1.filename)
        log(f"C.export_key={key}")
        log(f"C.storage_uri={inputs1.storage_uri}")
        actual_uri = put_local_file(Path(exec_result.output_path), key)
        log(f"C.actual_uri_after_upload={actual_uri}")
        scheme, parsed = parse_storage_uri(inputs1.storage_uri)
        log(f"C.parsed_scheme={scheme}")
        if scheme != "local":
            log(f"FAIL.C: expected local scheme, got {scheme}")
            return 11
        stored_path = Path(parsed)
        log(f"C.stored_path.exists={stored_path.exists()} bytes={stored_path.stat().st_size}")
        if not stored_path.exists():
            log("FAIL.C: storage URI does not resolve to an existing file")
            return 12
        if stored_path.stat().st_size != inputs1.content_bytes:
            log(
                f"FAIL.C: stored bytes {stored_path.stat().st_size} != "
                f"inputs.content_bytes {inputs1.content_bytes}"
            )
            return 13

        # --- sub-test D: persist + lineage --------------------------------
        export_row = persist_export_artifact(
            db, job=job, render_output=ro_row, inputs=inputs1,
            status=ExportArtifactStatus.UPLOADED,
        )
        db.commit()
        log(f"D.persisted.id={export_row.id}")
        log(f"D.persisted.render_output_id={export_row.render_output_id}")
        log(f"D.persisted.status={export_row.export_status}")
        log(f"D.persisted.platform={export_row.platform}")
        log(f"D.persisted.export_version={export_row.export_version}")
        log(f"D.persisted.export_hash={export_row.export_hash}")
        log(f"D.persisted.content_hash={export_row.content_hash}")
        log(f"D.persisted.filename={export_row.filename}")
        log(f"D.persisted.storage_uri={export_row.storage_uri}")
        if export_row.render_output_id != ro_row.id:
            log("FAIL.D: lineage broken: export.render_output_id != render_output.id")
            return 14
        if export_row.tenant_id != ro_row.tenant_id:
            log("FAIL.D: tenant_id mismatch between export and render output")
            return 15

        # --- sub-test E: idempotency / version bump ----------------------
        inputs_v2 = build_export_artifact(
            render_output=ro_row, tenant_slug=tenant.slug,
            candidate_id=cand_uuid, platform=target_manifest.platform,
            local_source_path=Path(exec_result.output_path),
            export_version=2,
        )
        log(f"E.v2.export_hash={inputs_v2.export_hash}")
        log(f"E.v2.content_hash={inputs_v2.content_hash}")
        if inputs_v2.export_hash == inputs1.export_hash:
            log("FAIL.E: export_hash did not change when version bumped")
            return 16
        if inputs_v2.content_hash != inputs1.content_hash:
            log(
                "FAIL.E: content_hash drifted across version bump — "
                "should be identical for the same file bytes"
            )
            return 17

        # --- sub-test F: usage events ------------------------------------
        usage = db.execute(select(UsageEvent)).scalars().all()
        events = sorted({(u.event_type, u.unit) for u in usage})
        log(f"F.usage_events={json.dumps(events)}")
        export_created = [u for u in usage if u.event_type == "export_created"]
        log(f"F.export_created.count={len(export_created)}")
        if len(export_created) != 1:
            log(f"FAIL.F: expected 1 export_created event, got {len(export_created)}")
            return 18
        meta = export_created[0].event_metadata or {}
        required_keys = {
            "export_id", "render_output_id", "platform", "export_version",
            "export_hash", "content_hash", "content_bytes", "storage_uri",
            "filename",
        }
        log(f"F.export_created.metadata_keys={sorted(meta.keys())}")
        if not required_keys.issubset(set(meta.keys())):
            log(f"FAIL.F: missing metadata keys {required_keys - set(meta.keys())}")
            return 19

        # Per-row DB readback
        all_exports = db.execute(select(ExportArtifact)).scalars().all()
        log(f"db.exports_count={len(all_exports)}")
        if len(all_exports) != 1:
            log(f"FAIL: expected 1 exports row, got {len(all_exports)}")
            return 20

    log("sub-tests A/B/C/D/E/F: OK")
    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
