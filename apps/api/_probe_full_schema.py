"""Full schema probe — drives `alembic upgrade head` then asserts that
every one of the 15 application tables, every key index, and every key
foreign key chain is present on the live DB.

`_probe_schema.py` only sees the 10 tables registered with
`Base.metadata.create_all`; this probe sees the schema **as Alembic
actually applies it**, which is the authoritative shape used in
development and (eventually) production.

Distinct non-zero exit codes per assertion failure so the proof log
points straight at the failing predicate:

  2 — alembic import failed
  3 — alembic.ini missing
  4 — alembic upgrade failed
  5 — sqlalchemy import failed
  6 — application table missing
  7 — required index missing
  8 — required unique index lacked unique=True
  9 — required foreign key missing or pointing to the wrong target
 10 — wrong number of application tables
"""
from __future__ import annotations

import io
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_full_schema.out"
PROBE_DB = Path(__file__).parent / "aidirector_full_schema_probe.db"

# The complete set of application tables Alembic should own after
# upgrading to head. `alembic_version` is bookkeeping, not application.
EXPECTED_APP_TABLES = {
    "tenants",
    "users",
    "uploads",
    "jobs",
    "scenes",
    "clip_candidates",
    "director_plans",
    "render_jobs",
    "render_outputs",
    "exports",
    "engagement_events",
    "experiment_groups",
    "performance_feature_sets",
    "ranking_snapshots",
    "usage_events",
}

# (table, index_name, must_be_unique)
REQUIRED_INDEXES: list[tuple[str, str, bool]] = [
    # Phase 6 — two-hash identity gate
    ("exports", "ix_exports_export_hash", True),
    ("exports", "ix_exports_content_hash", False),
    # Phase 7 — evaluator idempotency
    ("performance_feature_sets", "ix_pfs_export_id_feature_version", True),
    # Phase 8 — ranking snapshot idempotency
    ("ranking_snapshots", "ix_ranking_snapshots_candidate_feature_version", True),
    # Phase 10 — render idempotency + stale worker sweep
    ("render_jobs", "ix_render_jobs_idempotency_key", True),
    ("render_jobs", "ix_render_jobs_heartbeat_at", False),
    # Tenant-scoped read paths
    ("uploads", "ix_uploads_tenant_id_created_at", False),
    ("jobs", "ix_jobs_tenant_id_status", False),
    ("engagement_events", "ix_engagement_events_export_id", False),
    ("usage_events", "ix_usage_events_tenant_id_created_at", False),
    # Trust-gradient anchor
    ("performance_feature_sets", "ix_pfs_tenant_id_evaluated_at", False),
]

# (table, column, referred_table) — the FK chains that hold the
# tenant-scoped pipeline together.
REQUIRED_FOREIGN_KEYS: list[tuple[str, str, str]] = [
    # Tenant scoping
    ("uploads", "tenant_id", "tenants"),
    ("jobs", "tenant_id", "tenants"),
    ("scenes", "tenant_id", "tenants"),
    ("clip_candidates", "tenant_id", "tenants"),
    ("director_plans", "tenant_id", "tenants"),
    ("render_jobs", "tenant_id", "tenants"),
    ("render_outputs", "tenant_id", "tenants"),
    ("exports", "tenant_id", "tenants"),
    ("engagement_events", "tenant_id", "tenants"),
    ("experiment_groups", "tenant_id", "tenants"),
    ("performance_feature_sets", "tenant_id", "tenants"),
    ("ranking_snapshots", "tenant_id", "tenants"),
    ("usage_events", "tenant_id", "tenants"),
    # Pipeline chain
    ("jobs", "upload_id", "uploads"),
    ("scenes", "job_id", "jobs"),
    ("clip_candidates", "job_id", "jobs"),
    ("clip_candidates", "scene_id", "scenes"),
    ("director_plans", "job_id", "jobs"),
    ("render_jobs", "job_id", "jobs"),
    ("render_jobs", "candidate_id", "clip_candidates"),
    ("render_outputs", "render_job_id", "render_jobs"),
    # Export + telemetry chain
    ("exports", "render_output_id", "render_outputs"),
    ("engagement_events", "export_id", "exports"),
    ("performance_feature_sets", "export_id", "exports"),
    ("performance_feature_sets", "experiment_group_id", "experiment_groups"),
    # Ranking snapshot back-references
    ("ranking_snapshots", "candidate_id", "clip_candidates"),
    ("ranking_snapshots", "job_id", "jobs"),
    ("ranking_snapshots", "source_export_id", "exports"),
]


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
    log(f"cwd={os.getcwd()}")

    sys.path.insert(0, str(Path(__file__).parent / "src"))

    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        log("ALEMBIC IMPORT FAILED:")
        log(traceback.format_exc())
        return 2

    cfg_path = Path(__file__).parent / "alembic.ini"
    if not cfg_path.exists():
        log(f"missing alembic.ini at {cfg_path}")
        return 3

    cfg = Config(str(cfg_path))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    buf_out, buf_err = io.StringIO(), io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf_out, buf_err
    try:
        command.upgrade(cfg, "head")
        rc = 0
    except Exception:
        log("UPGRADE FAILED:")
        log(traceback.format_exc())
        rc = 4
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err

    log("--- alembic stdout ---")
    log(buf_out.getvalue() or "(empty)")
    log("--- alembic stderr ---")
    log(buf_err.getvalue() or "(empty)")

    if rc != 0:
        return rc

    try:
        from sqlalchemy import create_engine, inspect, text
    except Exception:
        log("SQLALCHEMY IMPORT FAILED:")
        log(traceback.format_exc())
        return 5

    engine = create_engine(os.environ["DATABASE_URL"])
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    log(f"live_tables={sorted(tables)}")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        log(f"alembic_version={version}")

    # --- assertion 1: every expected app table is present ----------------
    missing_tables = EXPECTED_APP_TABLES - tables
    if missing_tables:
        log(f"FAIL missing application tables: {sorted(missing_tables)}")
        return 6
    log(f"PASS all {len(EXPECTED_APP_TABLES)} application tables present")

    # --- assertion 2: total app table count is exactly right -------------
    app_tables = tables - {"alembic_version"}
    if app_tables != EXPECTED_APP_TABLES:
        unexpected = app_tables - EXPECTED_APP_TABLES
        log(f"FAIL unexpected tables present: {sorted(unexpected)}")
        return 10
    log(f"PASS table count exact: {len(app_tables)} application tables")

    # --- assertion 3: required indexes present + uniqueness honored ------
    for table_name, index_name, must_be_unique in REQUIRED_INDEXES:
        idx_rows = inspector.get_indexes(table_name)
        match = next((i for i in idx_rows if i["name"] == index_name), None)
        if match is None:
            log(f"FAIL missing index {table_name}.{index_name}")
            log(f"  available on {table_name}: {[i['name'] for i in idx_rows]}")
            return 7
        if must_be_unique and not match.get("unique", False):
            log(f"FAIL index {table_name}.{index_name} should be UNIQUE")
            return 8
        log(
            f"PASS index {table_name}.{index_name} "
            f"(unique={match.get('unique', False)}, cols={match.get('column_names')})"
        )

    # --- assertion 4: required foreign key chain is intact ---------------
    for table_name, column, referred_table in REQUIRED_FOREIGN_KEYS:
        fks = inspector.get_foreign_keys(table_name)
        match = next(
            (
                fk
                for fk in fks
                if column in (fk.get("constrained_columns") or [])
                and fk.get("referred_table") == referred_table
            ),
            None,
        )
        if match is None:
            log(f"FAIL missing FK {table_name}.{column} -> {referred_table}")
            log(f"  available FKs on {table_name}: {fks}")
            return 9
        log(f"PASS fk {table_name}.{column} -> {referred_table}")

    # --- column inventory for the proof log ------------------------------
    log("--- column inventory ---")
    for name in sorted(app_tables):
        cols = [c["name"] for c in inspector.get_columns(name)]
        log(f"  {name}: {len(cols)} cols = {cols}")

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
