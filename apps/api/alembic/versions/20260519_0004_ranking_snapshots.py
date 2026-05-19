"""ranking_snapshots

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-19

Adds the `ranking_snapshots` table for explainable, replayable ranking
audit. One row per (candidate × feature_version). UNIQUE index on
(candidate_id, feature_version) enforces idempotent upserts so re-running
the ranker for the same candidate produces the same row, not duplicates.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ranking_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("source_export_id", sa.Uuid(), nullable=True),
        sa.Column("base_rank_score", sa.Float(), nullable=False),
        sa.Column("engagement_adjustment", sa.Float(), nullable=False),
        sa.Column("final_rank_score", sa.Float(), nullable=False),
        sa.Column("feature_version", sa.String(32), nullable=False),
        sa.Column("feedback_applied", sa.Boolean(), nullable=False),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("engagement_weight_cap", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("snapshot_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_ranking_snapshots_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["clip_candidates.id"],
            name=op.f("fk_ranking_snapshots_candidate_id_clip_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_ranking_snapshots_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_export_id"], ["exports.id"],
            name=op.f("fk_ranking_snapshots_source_export_id_exports"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ranking_snapshots")),
    )
    op.create_index(
        "ix_ranking_snapshots_candidate_feature_version",
        "ranking_snapshots", ["candidate_id", "feature_version"], unique=True,
    )
    op.create_index(
        "ix_ranking_snapshots_tenant_id_created_at",
        "ranking_snapshots", ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_ranking_snapshots_feedback_applied",
        "ranking_snapshots", ["feedback_applied"],
    )
    op.create_index(
        "ix_ranking_snapshots_job_id",
        "ranking_snapshots", ["job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ranking_snapshots_job_id", "ranking_snapshots")
    op.drop_index("ix_ranking_snapshots_feedback_applied", "ranking_snapshots")
    op.drop_index("ix_ranking_snapshots_tenant_id_created_at", "ranking_snapshots")
    op.drop_index("ix_ranking_snapshots_candidate_feature_version", "ranking_snapshots")
    op.drop_table("ranking_snapshots")
