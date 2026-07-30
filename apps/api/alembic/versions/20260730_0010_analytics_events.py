"""Add first-party analytics events.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=False),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("project_id", sa.String(128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "event_id", name="uq_analytics_events_tenant_event"),
    )
    op.create_index("ix_analytics_events_tenant_created", "analytics_events", ["tenant_id", "created_at"])
    op.create_index("ix_analytics_events_name_created", "analytics_events", ["event_name", "created_at"])


def downgrade() -> None:
    op.drop_table("analytics_events")
