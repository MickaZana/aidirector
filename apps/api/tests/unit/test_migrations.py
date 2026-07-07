"""Migration consistency + startup-check unit tests.

These run without a live database — they only inspect Alembic metadata and
the settings object. No I/O, no network, fast.
"""
from __future__ import annotations


class TestAlembicMigrations:
    def test_single_head(self):
        """Exactly one migration head — no diverged branches."""
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        assert len(heads) == 1, (
            f"Multiple alembic heads detected: {heads}. "
            "Squash the branches before merging."
        )

    def test_revision_chain_has_no_gaps(self):
        """Every revision in the chain is reachable from the base."""
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        # walk_revisions() raises if there are orphaned revisions
        revisions = list(script.walk_revisions())
        assert len(revisions) >= 1

    def test_head_includes_every_migration_file(self):
        """The head's ancestry must include every file in versions/ — catches a
        new migration added without being chained in as the new head (which
        would silently leave it unreachable and unapplied)."""
        from pathlib import Path
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()

        chain = list(script.walk_revisions(base="base", head=head))
        file_count = len(
            [f for f in Path(script.versions).glob("*.py") if f.name != "__init__.py"]
        )
        assert len(chain) == file_count, (
            f"Head {head!r} reaches {len(chain)} revisions but {file_count} migration "
            "files exist — a migration was added without chaining it in as the head "
            "(check its down_revision)."
        )

    def test_render_manifest_version_not_reset(self):
        """Guard against RENDER_MANIFEST_VERSION being reverted to '1'."""
        from api.schemas.render_manifest import RENDER_MANIFEST_VERSION
        assert RENDER_MANIFEST_VERSION != "1", (
            "RENDER_MANIFEST_VERSION was reset to '1'. "
            "Bump it whenever schema fields are added or removed."
        )

    def test_all_models_importable(self):
        """Every ORM model must import cleanly — catches missing __init__ exports."""
        from api.models import (  # noqa: F401
            BriefTemplate,
            ClipCandidate,
            DirectorPlan,
            EngagementEvent,
            ExportArtifact,
            Job,
            RankingSnapshot,
            RenderJob,
            RenderOutput,
            Scene,
            Tenant,
            Upload,
            UsageEvent,
            User,
        )


class TestStartupCheck:
    def test_raises_on_missing_database_url(self, monkeypatch):
        from unittest.mock import MagicMock
        from api.startup_check import check_env

        settings = MagicMock()
        settings.database_url = ""
        settings.redis_url = "redis://localhost"
        settings.clerk_secret_key = "sk_test_x"
        settings.clerk_publishable_key = "pk_test_x"
        settings.clerk_webhook_secret = "whsec_x"
        # warn-only fields
        for attr in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key",
                     "r2_bucket", "stripe_secret_key", "stripe_webhook_secret",
                     "anthropic_api_key", "provenance_signing_key_b64",
                     "sentry_dsn", "logfire_token"):
            setattr(settings, attr, "")

        import pytest
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            check_env(settings)

    def test_raises_on_missing_redis_url(self, monkeypatch):
        from unittest.mock import MagicMock
        from api.startup_check import check_env

        settings = MagicMock()
        settings.database_url = "postgresql://x"
        settings.redis_url = ""
        settings.clerk_secret_key = "sk_test_x"
        settings.clerk_publishable_key = "pk_test_x"
        settings.clerk_webhook_secret = "whsec_x"
        for attr in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key",
                     "r2_bucket", "stripe_secret_key", "stripe_webhook_secret",
                     "anthropic_api_key", "provenance_signing_key_b64",
                     "sentry_dsn", "logfire_token"):
            setattr(settings, attr, "")

        import pytest
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            check_env(settings)

    def test_passes_with_all_critical_set(self):
        from unittest.mock import MagicMock
        from api.startup_check import check_env

        settings = MagicMock()
        settings.database_url = "postgresql://x"
        settings.redis_url = "redis://x"
        settings.clerk_secret_key = "sk_test_x"
        settings.clerk_publishable_key = "pk_test_x"
        settings.clerk_webhook_secret = "whsec_x"
        for attr in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key",
                     "r2_bucket", "stripe_secret_key", "stripe_webhook_secret",
                     "anthropic_api_key", "provenance_signing_key_b64",
                     "sentry_dsn", "logfire_token"):
            setattr(settings, attr, "")

        # Must not raise
        check_env(settings)

    def test_warns_but_does_not_raise_on_missing_optional(self, caplog):
        import logging
        from unittest.mock import MagicMock
        from api.startup_check import check_env

        settings = MagicMock()
        settings.database_url = "postgresql://x"
        settings.redis_url = "redis://x"
        settings.clerk_secret_key = "sk_test_x"
        settings.clerk_publishable_key = "pk_test_x"
        settings.clerk_webhook_secret = "whsec_x"
        # All optional fields empty
        for attr in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key",
                     "r2_bucket", "stripe_secret_key", "stripe_webhook_secret",
                     "anthropic_api_key", "provenance_signing_key_b64",
                     "sentry_dsn", "logfire_token"):
            setattr(settings, attr, "")

        with caplog.at_level(logging.WARNING, logger="api.startup_check"):
            check_env(settings)

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) > 0, "Expected warnings for missing optional vars"
