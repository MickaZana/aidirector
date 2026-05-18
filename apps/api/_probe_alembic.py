"""Drives `alembic upgrade head` from Python so we capture all output reliably."""
import io
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_alembic.out"
PROBE_DB = Path(__file__).parent / "aidirector_probe.db"


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

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    saved_out, saved_err = sys.stdout, sys.stderr
    sys.stdout = buf_out
    sys.stderr = buf_err
    try:
        command.upgrade(cfg, "head")
        rc = 0
    except Exception:
        log("UPGRADE FAILED:")
        log(traceback.format_exc())
        rc = 4
    finally:
        sys.stdout = saved_out
        sys.stderr = saved_err

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
    tables = sorted(inspector.get_table_names())
    log(f"tables_after_upgrade={tables}")

    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        log(f"alembic_version={version}")

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
