"""initial

Revision ID: 0001
Revises:
Create Date: 2026-05-18

Creates the AI Director multi-tenant base schema:
- tenants, users
- uploads, jobs
- scenes, clip_candidates, director_plans
- render_jobs, render_outputs
- usage_events
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenants")),
        sa.UniqueConstraint("slug", name=op.f("uq_tenants_slug")),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("clerk_user_id", sa.String(64), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_users_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("clerk_user_id", name=op.f("uq_users_clerk_user_id")),
    )
    op.create_index("ix_users_tenant_id_email", "users", ["tenant_id", "email"], unique=True)

    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("r2_key", sa.String(512), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("sport", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("upload_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_uploads_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_uploads_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_uploads")),
    )
    op.create_index("ix_uploads_tenant_id_created_at", "uploads", ["tenant_id", "created_at"])
    op.create_index("ix_uploads_status", "uploads", ["status"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("intent", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("omegaclips_job_id", sa.String(64), nullable=True),
        sa.Column("intel_submodule_sha", sa.String(40), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("cost_budget_cents", sa.Integer(), nullable=False),
        sa.Column("cost_actual_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_jobs_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"], ["uploads.id"], name=op.f("fk_jobs_upload_id_uploads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index("ix_jobs_tenant_id_status", "jobs", ["tenant_id", "status"])
    op.create_index("ix_jobs_upload_id", "jobs", ["upload_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    op.create_table(
        "scenes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("t_start", sa.Float(), nullable=False),
        sa.Column("t_end", sa.Float(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("arc_position", sa.String(16), nullable=True),
        sa.Column("intensity", sa.Float(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=True),
        sa.Column("signals", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_scenes_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_scenes_tenant_id_tenants"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenes")),
    )
    op.create_index("ix_scenes_job_id", "scenes", ["job_id"])
    op.create_index("ix_scenes_kind", "scenes", ["kind"])

    op.create_table(
        "clip_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("scene_id", sa.Uuid(), nullable=True),
        sa.Column("t_start", sa.Float(), nullable=False),
        sa.Column("t_end", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("platform_score", sa.Float(), nullable=True),
        sa.Column("virality_score", sa.Float(), nullable=True),
        sa.Column("novelty_score", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_clip_candidates_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_clip_candidates_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scene_id"], ["scenes.id"],
            name=op.f("fk_clip_candidates_scene_id_scenes"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clip_candidates")),
    )
    op.create_index("ix_clip_candidates_job_id", "clip_candidates", ["job_id"])
    op.create_index("ix_clip_candidates_scene_id", "clip_candidates", ["scene_id"])

    op.create_table(
        "director_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_director_plans_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_director_plans_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_director_plans")),
    )
    op.create_index("ix_director_plans_job_id", "director_plans", ["job_id"])
    op.create_index("ix_director_plans_created_at", "director_plans", ["created_at"])

    op.create_table(
        "render_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline", sa.String(32), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("gpu_seconds", sa.Float(), nullable=True),
        sa.Column("cost_cents", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_render_jobs_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_render_jobs_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["clip_candidates.id"],
            name=op.f("fk_render_jobs_candidate_id_clip_candidates"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_render_jobs")),
    )
    op.create_index("ix_render_jobs_job_id", "render_jobs", ["job_id"])
    op.create_index("ix_render_jobs_status", "render_jobs", ["status"])
    op.create_index("ix_render_jobs_created_at", "render_jobs", ["created_at"])

    op.create_table(
        "render_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("render_job_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("r2_key", sa.String(512), nullable=False),
        sa.Column("aspect_ratio", sa.String(8), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=True),
        sa.Column("bytes", sa.Integer(), nullable=True),
        sa.Column("output_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["render_job_id"], ["render_jobs.id"],
            name=op.f("fk_render_outputs_render_job_id_render_jobs"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_render_outputs_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_render_outputs")),
    )
    op.create_index("ix_render_outputs_render_job_id", "render_outputs", ["render_job_id"])

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("upload_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("estimated_cost_cents", sa.Integer(), nullable=True),
        sa.Column("stripe_meter_event_id", sa.String(64), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_usage_events_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_usage_events_user_id_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["upload_id"], ["uploads.id"],
            name=op.f("fk_usage_events_upload_id_uploads"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_usage_events_job_id_jobs"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_events")),
    )
    op.create_index(
        "ix_usage_events_tenant_id_created_at", "usage_events", ["tenant_id", "created_at"]
    )
    op.create_index("ix_usage_events_event_type", "usage_events", ["event_type"])
    op.create_index("ix_usage_events_job_id", "usage_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_events_job_id", "usage_events")
    op.drop_index("ix_usage_events_event_type", "usage_events")
    op.drop_index("ix_usage_events_tenant_id_created_at", "usage_events")
    op.drop_table("usage_events")

    op.drop_index("ix_render_outputs_render_job_id", "render_outputs")
    op.drop_table("render_outputs")

    op.drop_index("ix_render_jobs_created_at", "render_jobs")
    op.drop_index("ix_render_jobs_status", "render_jobs")
    op.drop_index("ix_render_jobs_job_id", "render_jobs")
    op.drop_table("render_jobs")

    op.drop_index("ix_director_plans_created_at", "director_plans")
    op.drop_index("ix_director_plans_job_id", "director_plans")
    op.drop_table("director_plans")

    op.drop_index("ix_clip_candidates_scene_id", "clip_candidates")
    op.drop_index("ix_clip_candidates_job_id", "clip_candidates")
    op.drop_table("clip_candidates")

    op.drop_index("ix_scenes_kind", "scenes")
    op.drop_index("ix_scenes_job_id", "scenes")
    op.drop_table("scenes")

    op.drop_index("ix_jobs_created_at", "jobs")
    op.drop_index("ix_jobs_upload_id", "jobs")
    op.drop_index("ix_jobs_tenant_id_status", "jobs")
    op.drop_table("jobs")

    op.drop_index("ix_uploads_status", "uploads")
    op.drop_index("ix_uploads_tenant_id_created_at", "uploads")
    op.drop_table("uploads")

    op.drop_index("ix_users_tenant_id_email", "users")
    op.drop_table("users")

    op.drop_table("tenants")
