"""Add pipeline_timing JSON column to jobs

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-05

Adds a JSON column to track per-stage timing breakdown for pipeline
performance analysis (Sprint 5.4 optimization).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("pipeline_timing", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "pipeline_timing")
