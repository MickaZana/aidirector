"""Migration-0005 isolation probe.

Separates Alembic 0005-specific problems from any operational-probe noise.

Steps:
  1. Drop any prior probe DB.
  2. Run `alembic upgrade 0004` (everything PRIOR to Phase 10).
  3. Snapshot tables / columns / indexes.
  4. Run `alembic upgrade 0005` (Phase 10 operational migration).
  5. Diff: new columns + new indexes match expectations.
  6. Downgrade 0005 → 0004; verify columns + indexes are gone.
  7. Exit 0.

Distinct rc per failure:
  2 — alembic import failed
  3 — upgrade to 0004 failed
  4 — pre-0005 snapshot wrong shape
  5 — upgrade 0004 → 0005 failed
  6 — 0005 didn't add expected columns
  7 — 0005 didn't add expected indexes
  8 — 0005 unique constraint missing or wrong
  9 — downgrade 0005 → 0004 failed
 10 — downgrade left columns/indexes behind

Every step writes a line to `_probe_migration_0005_only.out` BEFORE
starting work, so a hang shows the exact offending step.
"""
from __future__ import annotations

import io
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_migration_0005_only.out"
DB = Path(__file__).parent / "aidirector_migration_0005_probe.db"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def _capture_alembic(cfg, action: str, target: str) -> int:
    """Run an alembic action with stdout/stderr captured; log it."""
    from alembic import command  # noqa: PLC0415

    log(f"-> alembic {action} {target}")
    buf_out, buf_err = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf_out, buf_err
    try:
        if action == "upgrade":
            command.upgrade(cfg, target)
        elif action == "downgrade":
            command.downgrade(cfg, target)
        else:
            raise ValueError(f"unknown action {action}")
        rc = 0
    except Exception:
        log("ALEMBIC FAILED:")
        log(traceback.format_exc())
        rc = 1
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err
    if buf_out.getvalue():
        log("stdout: " + buf_out.getvalue().rstrip())
    if buf_err.getvalue():
        log("stderr: " + buf_err.getvalue().rstrip())
    return rc


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    if DB.exists():
        DB.unlink()
        log(f"deleted prior DB {DB}")

    os.environ["DATABASE_URL"] = f"sqlite:///{DB.as_posix()}"
    sys.path.insert(0, str(Path(__file__).parent / "src"))
    log(f"DATABASE_URL={os.environ['DATABASE_URL']}")

    log("step A: import alembic")
    try:
        from alembic.config import Config
        from sqlalchemy import create_engine, inspect, text
    except Exception:
        log("IMPORT FAILED:")
        log(traceback.format_exc())
        return 2
    log("step A: imports OK")

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    log("step A: alembic Config created")

    # --- upgrade to 0004 -----------------------------------------------
    if _capture_alembic(cfg, "upgrade", "0004") != 0:
        return 3
    log("step B: upgraded to 0004 OK")

    engine = create_engine(os.environ["DATABASE_URL"])
    insp = inspect(engine)
    pre_jobs = {c["name"] for c in insp.get_columns("jobs")}
    pre_render_jobs = {c["name"] for c in insp.get_columns("render_jobs")}
    pre_render_jobs_idx = {i["name"] for i in insp.get_indexes("render_jobs")}
    log(f"step B: jobs cols at 0004 = {sorted(pre_jobs)}")
    log(f"step B: render_jobs cols at 0004 = {sorted(pre_render_jobs)}")
    log(f"step B: render_jobs indexes at 0004 = {sorted(pre_render_jobs_idx)}")

    new_cols_expected = {"worker_id", "started_at", "heartbeat_at", "retry_count"}
    if pre_jobs & new_cols_expected:
        log(f"step B: FAIL — pre-0005 jobs already has Phase 10 cols: {pre_jobs & new_cols_expected}")
        return 4
    if pre_render_jobs & (new_cols_expected | {"idempotency_key"}):
        log(f"step B: FAIL — pre-0005 render_jobs already has Phase 10 cols")
        return 4
    log("step B: pre-0005 shape clean — no Phase 10 columns yet")

    # --- upgrade to 0005 -----------------------------------------------
    if _capture_alembic(cfg, "upgrade", "0005") != 0:
        return 5
    log("step C: upgraded 0004 -> 0005 OK")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        log(f"step C: alembic_version = {version}")

    insp = inspect(engine)
    post_jobs = {c["name"] for c in insp.get_columns("jobs")}
    post_render_jobs = {c["name"] for c in insp.get_columns("render_jobs")}
    post_render_jobs_idx = {i["name"]: i for i in insp.get_indexes("render_jobs")}
    log(f"step C: jobs cols at 0005 = {sorted(post_jobs)}")
    log(f"step C: render_jobs cols at 0005 = {sorted(post_render_jobs)}")
    log(f"step C: render_jobs indexes at 0005 = {sorted(post_render_jobs_idx.keys())}")

    if not new_cols_expected.issubset(post_jobs):
        log(f"step C: FAIL — jobs missing new cols: {new_cols_expected - post_jobs}")
        return 6
    if not (new_cols_expected | {"idempotency_key"}).issubset(post_render_jobs):
        log(
            f"step C: FAIL — render_jobs missing new cols: "
            f"{(new_cols_expected | {'idempotency_key'}) - post_render_jobs}"
        )
        return 6
    log("step C: PASS — 4 jobs cols + 5 render_jobs cols added")

    for want in ("ix_render_jobs_idempotency_key", "ix_render_jobs_heartbeat_at"):
        if want not in post_render_jobs_idx:
            log(f"step C: FAIL — missing index {want}")
            return 7
    log("step C: PASS — both new render_jobs indexes present")

    idem_ix = post_render_jobs_idx["ix_render_jobs_idempotency_key"]
    if not idem_ix.get("unique"):
        log(f"step C: FAIL — idempotency_key index not UNIQUE: {idem_ix}")
        return 8
    hb_ix = post_render_jobs_idx["ix_render_jobs_heartbeat_at"]
    if hb_ix.get("unique"):
        log(f"step C: FAIL — heartbeat_at index should NOT be unique: {hb_ix}")
        return 8
    log(
        f"step C: PASS — idempotency_key UNIQUE={idem_ix.get('unique')} cols={idem_ix.get('column_names')}, "
        f"heartbeat_at UNIQUE={hb_ix.get('unique')} cols={hb_ix.get('column_names')}"
    )

    # --- downgrade 0005 -> 0004 ---------------------------------------
    if _capture_alembic(cfg, "downgrade", "0004") != 0:
        return 9
    log("step D: downgraded 0005 -> 0004 OK")

    insp = inspect(engine)
    down_jobs = {c["name"] for c in insp.get_columns("jobs")}
    down_render_jobs = {c["name"] for c in insp.get_columns("render_jobs")}
    down_render_jobs_idx = {i["name"] for i in insp.get_indexes("render_jobs")}

    leftover_job_cols = down_jobs & new_cols_expected
    leftover_rj_cols = down_render_jobs & (new_cols_expected | {"idempotency_key"})
    leftover_idx = {"ix_render_jobs_idempotency_key", "ix_render_jobs_heartbeat_at"} & down_render_jobs_idx

    if leftover_job_cols or leftover_rj_cols or leftover_idx:
        log(
            f"step D: FAIL leftover after downgrade — "
            f"jobs={leftover_job_cols} render_jobs_cols={leftover_rj_cols} indexes={leftover_idx}"
        )
        return 10
    log("step D: PASS — downgrade dropped every Phase 10 column + index")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        log(f"step D: alembic_version after downgrade = {version}")

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
