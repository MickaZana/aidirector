"""Add marketplace columns to brief_templates

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-30

Adds is_public flag and use_count counter to BriefTemplate so templates can be
listed in the global marketplace and fork counts can be tracked.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "brief_templates",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "brief_templates",
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_brief_templates_is_public", "brief_templates", ["is_public"])


def downgrade() -> None:
    op.drop_index("ix_brief_templates_is_public", table_name="brief_templates")
    op.drop_column("brief_templates", "use_count")
    op.drop_column("brief_templates", "is_public")
