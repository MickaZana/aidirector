"""exports

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-19

Adds the `exports` table — canonical ExportArtifact identity layer.
Lineage to RenderOutput is FK-enforced; analytics attaches here, never
to render_outputs directly.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("render_output_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("export_status", sa.String(16), nullable=False),
        sa.Column("export_version", sa.Integer(), nullable=False),
        sa.Column("export_hash", sa.String(64), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_bytes", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("storage_uri", sa.String(512), nullable=False),
        sa.Column("artifact_metadata", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
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
            name=op.f("fk_exports_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["render_output_id"], ["render_outputs.id"],
            name=op.f("fk_exports_render_output_id_render_outputs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exports")),
    )
    op.create_index("ix_exports_tenant_id_platform", "exports", ["tenant_id", "platform"])
    op.create_index("ix_exports_tenant_id_created_at", "exports", ["tenant_id", "created_at"])
    op.create_index("ix_exports_render_output_id", "exports", ["render_output_id"])
    op.create_index("ix_exports_export_hash", "exports", ["export_hash"], unique=True)
    op.create_index("ix_exports_content_hash", "exports", ["content_hash"])
    op.create_index("ix_exports_export_status", "exports", ["export_status"])


def downgrade() -> None:
    op.drop_index("ix_exports_export_status", "exports")
    op.drop_index("ix_exports_content_hash", "exports")
    op.drop_index("ix_exports_export_hash", "exports")
    op.drop_index("ix_exports_render_output_id", "exports")
    op.drop_index("ix_exports_tenant_id_created_at", "exports")
    op.drop_index("ix_exports_tenant_id_platform", "exports")
    op.drop_table("exports")
