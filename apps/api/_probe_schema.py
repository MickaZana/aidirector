"""Base-model metadata probe (NOT the full schema proof).

Imports `api.models`, asks SQLAlchemy to materialise `Base.metadata` into
a throwaway SQLite DB, and dumps tables + columns + indexes. This proves
the ORM declarations themselves are import-clean and self-consistent.

It deliberately does **not** prove what production sees: only models that
end up in `Base.metadata` are reflected here, the DDL is whatever
`create_all` synthesises (no migration history, no per-revision DDL
differences), and Alembic is not exercised at all. Tables added to a
migration but not (yet) in `Base.metadata` would silently slip past this
probe.

For the authoritative schema proof — Alembic-applied DDL, the full
15-table set, unique indexes, and FK chains — see `_probe_full_schema.py`.
"""
import os
import sys
import traceback
from pathlib import Path

OUT = Path(__file__).parent / "_probe_schema.out"


def log(msg: str) -> None:
    with OUT.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    log(f"python={sys.version}")
    log(f"prefix={sys.prefix}")
    log(f"cwd={os.getcwd()}")

    sys.path.insert(0, str(Path(__file__).parent / "src"))
    log(f"sys.path[0]={sys.path[0]}")

    try:
        from api.models import Base  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        log("MODEL IMPORT FAILED:")
        log(traceback.format_exc())
        return 2

    log(f"tables={len(Base.metadata.tables)}")
    for name in sorted(Base.metadata.tables.keys()):
        t = Base.metadata.tables[name]
        log(f"  {name}: {len(t.columns)} cols, {len(t.indexes)} idx, {len(t.foreign_keys)} fk")

    try:
        from sqlalchemy import create_engine, inspect  # noqa: PLC0415

        engine = create_engine("sqlite:///./_probe_schema.db")
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        live_tables = sorted(inspector.get_table_names())
        log(f"live_tables={live_tables}")
        for name in live_tables:
            cols = [c["name"] for c in inspector.get_columns(name)]
            idx = [i["name"] for i in inspector.get_indexes(name)]
            log(f"  {name} cols={cols}")
            log(f"  {name} indexes={idx}")
    except Exception:  # noqa: BLE001
        log("CREATE_ALL FAILED:")
        log(traceback.format_exc())
        return 3

    log("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
