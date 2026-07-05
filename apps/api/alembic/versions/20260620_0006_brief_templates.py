"""Add brief_templates table

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-20

Stores reusable DirectorPlan brief presets per tenant. Fields map directly
to DirectorPlan editorial signals (sport, render_style, caption_style, pacing)
plus freeform hook_phrases and searchable tags (both JSON arrays).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brief_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sport", sa.String(64), nullable=True),
        sa.Column("render_style", sa.String(32), nullable=True),
        sa.Column("caption_style", sa.String(32), nullable=True),
        sa.Column("pacing", sa.String(16), nullable=True),
        sa.Column("hook_phrases", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brief_templates_tenant_id", "brief_templates", ["tenant_id"])
    op.create_index("ix_brief_templates_sport", "brief_templates", ["sport"])


def downgrade() -> None:
    op.drop_index("ix_brief_templates_sport", table_name="brief_templates")
    op.drop_index("ix_brief_templates_tenant_id", table_name="brief_templates")
    op.drop_table("brief_templates")
