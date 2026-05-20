"""operational state safety

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-19

Phase 10 operational fields:
  - jobs / render_jobs gain (worker_id, started_at, heartbeat_at, retry_count)
  - render_jobs gains UNIQUE(idempotency_key) so a duplicate retry of the
    same render fixture cannot produce a second row. The Pydantic-driven
    `services.idempotency.render_idempotency_key(...)` builds the value;
    the unique constraint is what enforces the safety.
  - render_jobs gains a non-unique index on heartbeat_at for the stale
    worker sweep.

No state column shape changes: `retrying` (8 chars) fits inside the
existing String(16) columns on jobs.status, render_jobs.status, and
exports.export_status.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- jobs --------------------------------------------------------------
    with op.batch_alter_table("jobs", schema=None) as batch:
        batch.add_column(sa.Column("worker_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )

    # --- render_jobs ------------------------------------------------------
    with op.batch_alter_table("render_jobs", schema=None) as batch:
        batch.add_column(sa.Column("worker_id", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
        batch.add_column(
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch.add_column(
            sa.Column("idempotency_key", sa.String(length=64), nullable=True)
        )

    op.create_index(
        "ix_render_jobs_idempotency_key",
        "render_jobs",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_render_jobs_heartbeat_at",
        "render_jobs",
        ["heartbeat_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_render_jobs_heartbeat_at", table_name="render_jobs")
    op.drop_index("ix_render_jobs_idempotency_key", table_name="render_jobs")
    with op.batch_alter_table("render_jobs", schema=None) as batch:
        batch.drop_column("idempotency_key")
        batch.drop_column("retry_count")
        batch.drop_column("heartbeat_at")
        batch.drop_column("started_at")
        batch.drop_column("worker_id")

    with op.batch_alter_table("jobs", schema=None) as batch:
        batch.drop_column("retry_count")
        batch.drop_column("heartbeat_at")
        batch.drop_column("started_at")
        batch.drop_column("worker_id")
