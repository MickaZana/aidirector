"""Add plan_corrections table for Adaptive Director Agent

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-05

Tracks user edits to DirectorPlans for the Sprint 5.3 learning loop.
Every correction snapshots the pre- and post-edited plan JSON so the
pipeline can be re-run with either version.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_corrections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("director_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_plan_json", sa.JSON(), nullable=False),
        sa.Column("corrected_plan_json", sa.JSON(), nullable=False),
        sa.Column("correction_type", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_corrections_tenant_id", "plan_corrections", ["tenant_id"])
    op.create_index("ix_plan_corrections_job_id", "plan_corrections", ["job_id"])
    op.create_index("ix_plan_corrections_plan_id", "plan_corrections", ["plan_id"])
    op.create_index("ix_plan_corrections_created_at", "plan_corrections", ["created_at"])


def downgrade() -> None:
    op.drop_table("plan_corrections")
