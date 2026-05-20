"""Phase 10 probe — operational state safety + cloud-readiness gates.

Sub-tests (distinct rc per failure):

  A — alembic upgrade head applies migration 0005 cleanly
  B — JOB_TRANSITIONS rejects illegal moves (succeeded → running, etc.)
  C — happy-path job lifecycle goes queued → running → succeeded through the guard
  D — failed → retrying → running → succeeded round-trip works
  E — render_jobs.idempotency_key is UNIQUE; duplicate insert raises IntegrityError;
      claim_render returns the existing row
  F — export_hash continues to enforce export uniqueness (claim_export)
  G — worker heartbeat: mark_worker_started/heartbeat updates the row;
      detect_stale_rows finds a row with an old heartbeat
  H — TRANSITION_REJECTED audit event is written on illegal transitions
  I — terminal-state protection: succeeded → anything is rejected
  J — force=True override moves into cancelled with TRANSITION_FORCED audit
  K — R2 path determinism: upload_key/render_key/export_key are stable
       across calls with the same inputs
  L — `r2.put_local_file` in local mode round-trips bytes and verifies
       the destination size
  M — `r2.signed_get_url` returns a local:// URI in local mode, an
       https:// URI in R2 mode (skipped unless R2 creds present)
  N — Cloud entrypoints discoverable: workers.modal_app exposes
       ping_intel, analyze_scene_fixture, rank_clip_candidates_fixture,
       render_one_fixture as Modal-decorated callables.

Modal cloud proof (rc=0 means LOCAL-EQUIVALENT PROVEN). For actual
distributed execution, the operator runs (commands echoed at the end
of the probe output):

    modal token new
    modal secret create aidirector ...
    modal run workers/src/workers/modal_app.py::ping_intel
    modal run workers/src/workers/modal_app.py::analyze_scene_fixture
    modal run workers/src/workers/modal_app.py::rank_clip_candidates_fixture
    modal run workers/src/workers/modal_app.py::render_one_fixture
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "_probe_phase10_cloud.out"
PROBE_DB = Path(__file__).parent / "aidirector_phase10_probe.db"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    if PROBE_DB.exists():
        PROBE_DB.unlink()

    os.environ["DATABASE_URL"] = f"sqlite:///{PROBE_DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))

    # --- A: alembic upgrade head -----------------------------------------
    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        log("A: FAIL alembic import"); log(traceback.format_exc()); return 2

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    buf_out, buf_err = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf_out, buf_err
    try:
        command.upgrade(cfg, "head")
    except Exception:
        log("A: FAIL alembic upgrade head"); log(traceback.format_exc()); return 3
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    log("A: PASS alembic upgrade head applied 0001..0005")

    from sqlalchemy import create_engine, inspect, select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    rj_cols = {c["name"] for c in inspector.get_columns("render_jobs")}
    jobs_cols = {c["name"] for c in inspector.get_columns("jobs")}
    if not {"worker_id", "started_at", "heartbeat_at", "retry_count"} <= rj_cols:
        log(f"A: FAIL render_jobs missing heartbeat cols, got {sorted(rj_cols)}"); return 4
    if "idempotency_key" not in rj_cols:
        log("A: FAIL render_jobs missing idempotency_key"); return 4
    if not {"worker_id", "started_at", "heartbeat_at", "retry_count"} <= jobs_cols:
        log(f"A: FAIL jobs missing heartbeat cols, got {sorted(jobs_cols)}"); return 4
    log(f"A: PASS migration 0005 added heartbeat + idempotency columns")

    # Index check via inspector
    rj_indexes = {i["name"]: i for i in inspector.get_indexes("render_jobs")}
    if not rj_indexes.get("ix_render_jobs_idempotency_key", {}).get("unique"):
        log("A: FAIL idempotency_key index not unique"); return 4
    if "ix_render_jobs_heartbeat_at" not in rj_indexes:
        log("A: FAIL heartbeat_at index missing"); return 4
    log("A: PASS render_jobs indexes: idempotency_key UNIQUE, heartbeat_at present")

    # --- B/C/D/H/I/J: state transitions ----------------------------------
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = SessionLocal()

    try:
        from api.models import (
            ClipCandidate,
            ExportArtifact,
            ExportArtifactStatus,
            Job,
            JobStatus,
            RenderJob,
            RenderJobStatus,
            RenderOutput,
            Scene,
            Tenant,
            Upload,
            UsageEvent,
            UsageEventType,
        )
        from api.services.idempotency import (
            claim_export,
            claim_render,
            export_idempotency_key,
            render_idempotency_key,
        )
        from api.services.operational_audit import (
            DEFAULT_STALE_AFTER,
            detect_stale_rows,
            mark_retry_initiated,
            mark_worker_heartbeat,
            mark_worker_started,
        )
        from api.services.state_transitions import (
            EXPORT_TRANSITIONS,
            IllegalTransition,
            JOB_TRANSITIONS,
            RENDER_JOB_TRANSITIONS,
            is_terminal,
            legal_transitions,
            transition,
        )
        from api.services import r2
    except Exception:
        log("import failed"); log(traceback.format_exc()); return 5

    # Seed a tenant + upload + candidate so we can construct render/export rows
    tenant = Tenant(id=uuid.uuid4(), slug="phase10", name="Phase10", plan="creator")
    db.add(tenant); db.flush()
    upload = Upload(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        r2_key=r2.upload_key(str(tenant.id), str(uuid.uuid4()), "sample.mp4"),
        filename="sample.mp4",
        bytes=10_000_000,
        sport="football",
        status="ready",
    )
    db.add(upload); db.flush()

    def _fresh_job() -> Job:
        j = Job(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            upload_id=upload.id,
            intent="analyze",
            status=JobStatus.QUEUED.value,
        )
        db.add(j); db.flush()
        return j

    # B — illegal moves rejected
    job_b = _fresh_job()
    try:
        transition(db, job_b, JobStatus.SUCCEEDED.value)
    except IllegalTransition as e:
        log(f"B: PASS queued -> succeeded rejected ({e.from_state} -> {e.to_state})")
    else:
        log("B: FAIL queued -> succeeded was NOT rejected"); return 6

    # C — happy path
    job_c = _fresh_job()
    transition(db, job_c, JobStatus.RUNNING.value, reason="analysis_started")
    transition(db, job_c, JobStatus.SUCCEEDED.value, reason="analysis_done")
    if job_c.status != JobStatus.SUCCEEDED.value:
        log(f"C: FAIL final status={job_c.status}"); return 7
    log("C: PASS queued -> running -> succeeded")

    # I — terminal-state protection
    try:
        transition(db, job_c, JobStatus.RUNNING.value)
    except IllegalTransition:
        log("I: PASS succeeded -> running rejected (terminal protected)")
    else:
        log("I: FAIL succeeded -> running was allowed"); return 8

    # D — retry path
    job_d = _fresh_job()
    transition(db, job_d, JobStatus.RUNNING.value)
    transition(db, job_d, JobStatus.FAILED.value, reason="simulated failure")
    transition(db, job_d, JobStatus.RETRYING.value, reason="retry")
    mark_retry_initiated(db, job_d, reason="explicit retry", by_worker="probe")
    transition(db, job_d, JobStatus.RUNNING.value, reason="retry-running")
    transition(db, job_d, JobStatus.SUCCEEDED.value, reason="retry-succeeded")
    if job_d.retry_count != 1 or job_d.status != JobStatus.SUCCEEDED.value:
        log(f"D: FAIL retry_count={job_d.retry_count} status={job_d.status}"); return 9
    log("D: PASS failed -> retrying -> running -> succeeded, retry_count=1")

    # J — admin force into cancelled
    job_j = _fresh_job()
    transition(db, job_j, JobStatus.RUNNING.value)
    transition(db, job_j, JobStatus.CANCELLED.value, force=True, reason="admin override")
    if job_j.status != JobStatus.CANCELLED.value:
        log(f"J: FAIL status={job_j.status}"); return 10
    log("J: PASS force=True allowed running -> cancelled")
    try:
        # force=True is narrow — cannot push into arbitrary states
        transition(db, _fresh_job(), JobStatus.SUCCEEDED.value, force=True)
    except IllegalTransition:
        log("J: PASS force=True is NOT a universal bypass (queued -> succeeded still rejected)")
    else:
        log("J: FAIL force=True bypassed all guards"); return 10

    # H — TRANSITION_REJECTED audit row was written
    db.commit()
    rejected = db.execute(
        select(UsageEvent).where(
            UsageEvent.event_type == UsageEventType.TRANSITION_REJECTED.value
        )
    ).scalars().all()
    if not rejected:
        log("H: FAIL no TRANSITION_REJECTED events written"); return 11
    log(f"H: PASS {len(rejected)} TRANSITION_REJECTED audit row(s) written")

    accepted = db.execute(
        select(UsageEvent).where(
            UsageEvent.event_type == UsageEventType.TRANSITION_ACCEPTED.value
        )
    ).scalars().all()
    if not accepted:
        log("H: FAIL no TRANSITION_ACCEPTED events written"); return 11
    log(f"H: PASS {len(accepted)} TRANSITION_ACCEPTED audit row(s) written")

    # --- E: render idempotency -----------------------------------------
    # Seed a Scene + ClipCandidate so render_jobs FKs resolve.
    scene = Scene(
        id=uuid.uuid4(),
        job_id=job_c.id,
        tenant_id=tenant.id,
        t_start=0.0, t_end=12.0, kind="goal",
        arc_position="climax", intensity=0.9, importance=0.85,
        signals={},
    )
    db.add(scene); db.flush()
    cand = ClipCandidate(
        id=uuid.uuid4(),
        job_id=job_c.id,
        tenant_id=tenant.id,
        scene_id=scene.id,
        t_start=0.0, t_end=12.0,
        confidence_score=0.8, quality_score=0.75, platform_score=0.7,
        rationale="seed",
        scores={},
    )
    db.add(cand); db.flush()

    key_inputs = dict(
        candidate_id=str(cand.id),
        variant_id="variant-yt-9x16",
        render_style="sports_hype",
        plan_version="1",
    )
    key = render_idempotency_key(**key_inputs)
    key_again = render_idempotency_key(**key_inputs)
    if key != key_again:
        log("E: FAIL render_idempotency_key is non-deterministic"); return 12

    rj1 = RenderJob(
        id=uuid.uuid4(),
        job_id=job_c.id,
        tenant_id=tenant.id,
        candidate_id=cand.id,
        pipeline="sports_hype",
        platform="youtube_shorts",
        status=RenderJobStatus.QUEUED.value,
        settings={},
        idempotency_key=key,
    )
    db.add(rj1); db.commit()

    # Duplicate insert with the same key — DB UNIQUE constraint MUST reject.
    rj2 = RenderJob(
        id=uuid.uuid4(),
        job_id=job_c.id,
        tenant_id=tenant.id,
        candidate_id=cand.id,
        pipeline="sports_hype",
        platform="youtube_shorts",
        status=RenderJobStatus.QUEUED.value,
        settings={},
        idempotency_key=key,
    )
    db.add(rj2)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        log("E: PASS duplicate render_jobs.idempotency_key raises IntegrityError")
    else:
        log("E: FAIL duplicate render_jobs.idempotency_key was allowed"); return 12

    existing = claim_render(db, idempotency_key=key)
    if existing is None or existing.id != rj1.id:
        log("E: FAIL claim_render did not return the existing row"); return 12
    log(f"E: PASS claim_render returns the original RenderJob {rj1.id}")

    # --- F: export idempotency via export_hash --------------------------
    ro = RenderOutput(
        id=uuid.uuid4(),
        render_job_id=rj1.id,
        tenant_id=tenant.id,
        r2_key=r2.render_key(str(tenant.id), str(rj1.id), "out.mp4"),
        aspect_ratio="9:16",
        duration_s=12.0,
        bytes=1_580_000,
        output_metadata={},
    )
    db.add(ro); db.flush()
    export_hash = export_idempotency_key(
        render_output_id=str(ro.id), platform="youtube_shorts", export_version=1,
    )
    exp = ExportArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        render_output_id=ro.id,
        platform="youtube_shorts",
        export_status=ExportArtifactStatus.PENDING.value,
        export_version=1,
        export_hash=export_hash,
        content_hash="c" * 64,
        content_bytes=1_580_000,
        filename="out.mp4",
        storage_uri=r2.build_storage_uri(ro.r2_key),
        artifact_metadata={},
    )
    db.add(exp); db.commit()

    # Duplicate same export_hash → UNIQUE violation
    dup = ExportArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        render_output_id=ro.id,
        platform="youtube_shorts",
        export_status=ExportArtifactStatus.PENDING.value,
        export_version=1,
        export_hash=export_hash,
        content_hash="c" * 64,
        content_bytes=1_580_000,
        filename="dup.mp4",
        storage_uri=r2.build_storage_uri(ro.r2_key),
        artifact_metadata={},
    )
    db.add(dup)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        log("F: PASS duplicate exports.export_hash raises IntegrityError")
    else:
        log("F: FAIL duplicate exports.export_hash was allowed"); return 13

    found = claim_export(db, export_hash=export_hash)
    if found is None or found.id != exp.id:
        log("F: FAIL claim_export did not find the original"); return 13
    log("F: PASS claim_export resolves to the original artifact")

    # Export transition guard: PENDING -> UPLOADED is illegal (must go via UPLOADING)
    try:
        transition(db, exp, ExportArtifactStatus.UPLOADED.value)
    except IllegalTransition:
        log("F: PASS export pending -> uploaded rejected (must traverse uploading)")
    else:
        log("F: FAIL export pending -> uploaded was allowed"); return 13
    transition(db, exp, ExportArtifactStatus.UPLOADING.value, reason="upload starting")
    transition(db, exp, ExportArtifactStatus.UPLOADED.value, reason="upload verified")
    db.commit()
    log(f"F: PASS export PENDING -> UPLOADING -> UPLOADED through guard")

    # --- G: heartbeat + stale detection --------------------------------
    rj1 = db.get(RenderJob, rj1.id)
    transition(db, rj1, RenderJobStatus.RENDERING.value, reason="start")
    mark_worker_started(db, rj1, worker_id="modal-pod-abc")
    db.flush()
    if rj1.worker_id != "modal-pod-abc" or rj1.heartbeat_at is None:
        log(f"G: FAIL worker_id={rj1.worker_id} heartbeat_at={rj1.heartbeat_at}"); return 14
    log(f"G: PASS worker_started set worker_id + heartbeat_at")

    first_hb = rj1.heartbeat_at
    mark_worker_heartbeat(
        db, rj1, worker_id="modal-pod-abc",
        now=first_hb + timedelta(seconds=30),
    )
    if rj1.heartbeat_at <= first_hb:
        log("G: FAIL heartbeat_at did not advance"); return 14
    log(f"G: PASS heartbeat bumps heartbeat_at forward by 30s")

    # Force a stale heartbeat and verify detection
    rj1.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    stale = detect_stale_rows(db, RenderJob, stale_after=DEFAULT_STALE_AFTER)
    if not stale or stale[0].id != rj1.id:
        log(f"G: FAIL stale detection missed the row (found {[s.id for s in stale]})"); return 14
    db.commit()
    stale_events = db.execute(
        select(UsageEvent).where(
            UsageEvent.event_type == UsageEventType.WORKER_STALE_DETECTED.value
        )
    ).scalars().all()
    if not stale_events:
        log("G: FAIL no WORKER_STALE_DETECTED event"); return 14
    log(f"G: PASS detect_stale_rows found the row + emitted {len(stale_events)} WORKER_STALE_DETECTED event(s)")

    # --- K: R2 path determinism -----------------------------------------
    tid = "tenant_demo_01"
    uid = "01913f78-1b6d-7c92-9a64-1a6b6b50c2f9"
    fn = "sample.mp4"
    k1 = r2.upload_key(tid, uid, fn)
    k2 = r2.upload_key(tid, uid, fn)
    if k1 != k2 or k1 != f"tenant/{tid}/upload/{uid}/{fn}":
        log(f"K: FAIL upload_key drift: {k1!r} vs {k2!r}"); return 15
    rk = r2.render_key(tid, "render-id-001", "out.mp4")
    ek = r2.export_key(tid, "export-id-001", "out.mp4")
    if not rk.startswith(f"tenant/{tid}/render/render-id-001/"):
        log(f"K: FAIL render_key: {rk!r}"); return 15
    if not ek.startswith(f"tenant/{tid}/exports/export-id-001/"):
        log(f"K: FAIL export_key: {ek!r}"); return 15
    log(f"K: PASS upload_key={k1}")
    log(f"K: PASS render_key={rk}")
    log(f"K: PASS export_key={ek}")

    # --- L: r2.put_local_file in local mode round-trips + verifies ------
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "src.bin"
        src.write_bytes(b"hello-phase10")
        os.environ["LOCAL_STORAGE_MIRROR"] = str(Path(td) / "mirror")
        key = r2.export_key(tid, "export-probe", "src.bin")
        result = r2.put_local_file(src, key, verify=True)
        if not result.verified or result.bytes != len(b"hello-phase10"):
            log(f"L: FAIL put_local_file result={result}"); return 16
        if not result.storage_uri.startswith("local://"):
            log(f"L: FAIL storage_uri not local: {result.storage_uri}"); return 16
        # round-trip through parse
        scheme, parsed = r2.parse_storage_uri(result.storage_uri)
        if scheme != "local" or not Path(parsed).exists():
            log(f"L: FAIL parse_storage_uri scheme={scheme} parsed={parsed}"); return 16
        head = r2.head_object(key)
        if head is None or head.get("ContentLength") != len(b"hello-phase10"):
            log(f"L: FAIL head_object={head}"); return 16
        log(f"L: PASS local upload verified, {result.bytes} bytes, head ContentLength={head['ContentLength']}")

    # --- M: signed_get_url shape ----------------------------------------
    url = r2.signed_get_url(key, expires_s=300)
    if r2.is_r2_configured():
        if not url.startswith("https://"):
            log(f"M: FAIL r2-mode signed_get_url not https: {url}"); return 17
        log(f"M: PASS r2-mode signed_get_url returned https URL ({len(url)} bytes)")
    else:
        if not url.startswith("local://"):
            log(f"M: FAIL local-mode signed_get_url: {url}"); return 17
        log(f"M: PASS local-mode signed_get_url returned local URI")
        log(f"M: NOTE r2.is_r2_configured()=False — set R2_* env vars to exercise the https path")

    # --- N: modal_app exposes the cloud entrypoints ---------------------
    try:
        from workers import modal_app as ma
    except Exception:
        log("N: FAIL workers.modal_app import"); log(traceback.format_exc()); return 18
    entrypoints = ["ping_intel", "analyze_scene_fixture", "rank_clip_candidates_fixture", "render_one_fixture"]
    for name in entrypoints:
        fn = getattr(ma, name, None)
        if fn is None or not hasattr(fn, "remote"):
            log(f"N: FAIL workers.modal_app.{name} is not a Modal function"); return 18
    log(f"N: PASS workers.modal_app exposes {len(entrypoints)} Modal entrypoints: {entrypoints}")

    # --- Operator handoff: what's left ----------------------------------
    log("")
    log("=== LOCAL-EQUIVALENT PROVEN ===")
    log("All state-safety, idempotency, heartbeat, stale-detection, R2-path,")
    log("local-upload, and Modal entrypoint registration assertions PASS.")
    log("")
    log("=== CLOUD PROOFS — REQUIRE OPERATOR ACTION ===")
    log("The following commands must be run by an operator with valid Modal")
    log("and Cloudflare R2 credentials. The probe cannot execute them.")
    log("")
    log("  modal token new")
    log("  modal secret create aidirector \\")
    log("      DATABASE_URL=$PROD_DATABASE_URL \\")
    log("      R2_ACCOUNT_ID=$R2_ACCOUNT_ID \\")
    log("      R2_ACCESS_KEY_ID=$R2_ACCESS_KEY_ID \\")
    log("      R2_SECRET_ACCESS_KEY=$R2_SECRET_ACCESS_KEY \\")
    log("      R2_BUCKET=$R2_BUCKET \\")
    log("      ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
    log("  modal run workers/src/workers/modal_app.py::ping_intel")
    log("  modal run workers/src/workers/modal_app.py::analyze_scene_fixture")
    log("  modal run workers/src/workers/modal_app.py::rank_clip_candidates_fixture")
    log("  modal run workers/src/workers/modal_app.py::render_one_fixture")
    log("")
    log("After R2 creds are present locally, this probe will also exercise")
    log("the https signed-URL branch and the HEAD-after-PUT verification path.")
    log("")
    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
