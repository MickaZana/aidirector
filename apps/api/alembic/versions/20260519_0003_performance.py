"""performance + engagement

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-19

Adds three tables for the measure → improve loop:
  - engagement_events       (raw telemetry, FK to exports)
  - experiment_groups       (A/B grouping primitive)
  - performance_feature_sets(derived ranker-consumable features)

Raw engagement cannot leak into ranking: the evaluator writes
performance_feature_sets and only that table is read by the
ranking_feedback_adapter.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- experiment_groups -------------------------------------------------
    op.create_table(
        "experiment_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_name", sa.String(128), nullable=False),
        sa.Column("experiment_version", sa.Integer(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("group_metadata", sa.JSON(), nullable=False),
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
            name=op.f("fk_experiment_groups_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiment_groups")),
    )
    op.create_index(
        "ix_experiment_groups_tenant_id_created_at",
        "experiment_groups", ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_experiment_groups_tenant_id_name",
        "experiment_groups", ["tenant_id", "experiment_name"],
    )

    # --- engagement_events -------------------------------------------------
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("metric_type", sa.String(32), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("observation_window_hours", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
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
            name=op.f("fk_engagement_events_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["export_id"], ["exports.id"],
            name=op.f("fk_engagement_events_export_id_exports"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_engagement_events")),
    )
    op.create_index(
        "ix_engagement_events_export_id",
        "engagement_events", ["export_id"],
    )
    op.create_index(
        "ix_engagement_events_tenant_id_observed_at",
        "engagement_events", ["tenant_id", "observed_at"],
    )
    op.create_index(
        "ix_engagement_events_platform_metric",
        "engagement_events", ["platform", "metric_type"],
    )
    op.create_index(
        "ix_engagement_events_dedup",
        "engagement_events", ["export_id", "platform", "metric_type", "observed_at"],
    )

    # --- performance_feature_sets -----------------------------------------
    op.create_table(
        "performance_feature_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("export_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_group_id", sa.Uuid(), nullable=True),
        sa.Column("feature_version", sa.String(32), nullable=False),
        sa.Column("maturity_state", sa.String(16), nullable=False),
        sa.Column("engagement_confidence", sa.Float(), nullable=False),
        sa.Column("normalized_view_rate", sa.Float(), nullable=True),
        sa.Column("normalized_completion_rate", sa.Float(), nullable=True),
        sa.Column("normalized_watch_time", sa.Float(), nullable=True),
        sa.Column("replay_rate", sa.Float(), nullable=True),
        sa.Column("share_rate", sa.Float(), nullable=True),
        sa.Column("engagement_score", sa.Float(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(), nullable=False),
        sa.Column("derived_metadata", sa.JSON(), nullable=False),
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
            name=op.f("fk_pfs_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["export_id"], ["exports.id"],
            name=op.f("fk_pfs_export_id_exports"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["experiment_group_id"], ["experiment_groups.id"],
            name=op.f("fk_pfs_experiment_group_id_experiment_groups"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performance_feature_sets")),
    )
    op.create_index(
        "ix_pfs_export_id_feature_version",
        "performance_feature_sets", ["export_id", "feature_version"],
        unique=True,
    )
    op.create_index(
        "ix_pfs_tenant_id_evaluated_at",
        "performance_feature_sets", ["tenant_id", "evaluated_at"],
    )
    op.create_index(
        "ix_pfs_experiment_group_id",
        "performance_feature_sets", ["experiment_group_id"],
    )
    op.create_index(
        "ix_pfs_maturity_state",
        "performance_feature_sets", ["maturity_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_pfs_maturity_state", "performance_feature_sets")
    op.drop_index("ix_pfs_experiment_group_id", "performance_feature_sets")
    op.drop_index("ix_pfs_tenant_id_evaluated_at", "performance_feature_sets")
    op.drop_index("ix_pfs_export_id_feature_version", "performance_feature_sets")
    op.drop_table("performance_feature_sets")

    op.drop_index("ix_engagement_events_dedup", "engagement_events")
    op.drop_index("ix_engagement_events_platform_metric", "engagement_events")
    op.drop_index("ix_engagement_events_tenant_id_observed_at", "engagement_events")
    op.drop_index("ix_engagement_events_export_id", "engagement_events")
    op.drop_table("engagement_events")

    op.drop_index("ix_experiment_groups_tenant_id_name", "experiment_groups")
    op.drop_index("ix_experiment_groups_tenant_id_created_at", "experiment_groups")
    op.drop_table("experiment_groups")
