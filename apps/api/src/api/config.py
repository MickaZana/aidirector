from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


_REPO_ROOT = Path(__file__).resolve().parents[4]
_WORKSPACE_ENV = _REPO_ROOT / ".env.local"


class Settings(BaseSettings):
    # Resolve the workspace env file from the module location so the API gets
    # the same configuration whether launched from the repo root or apps/api.
    model_config = SettingsConfigDict(env_file=str(_WORKSPACE_ENV), extra="ignore")

    env: Literal["development", "staging", "production"] = "development"

    database_url: str = ""
    redis_url: str = ""

    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""
    r2_public_base_url: str = ""

    clerk_publishable_key: str = ""
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_jwks_url: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_meter_asr_minutes: str = ""
    stripe_meter_gpu_seconds: str = ""
    stripe_meter_export_count: str = ""
    stripe_price_pro: str = ""
    stripe_price_studio: str = ""

    # pydantic-settings parses list fields from env as JSON, e.g.:
    #   ALLOWED_ORIGINS=["https://app.example.com","https://example.vercel.app"]
    # A bare comma-separated string ("a.com,b.com") raises a SettingsError at
    # startup — the whole app fails to boot, not just CORS.
    allowed_origins: list[str] = ["http://localhost:3000"]

    anthropic_api_key: str = ""
    deepgram_api_key: str = ""

    sentry_dsn: str = ""
    logfire_token: str = ""

    provenance_signing_key_b64: str = ""
    provenance_key_id: str = "default-v1"

    # Feature flags (Sprint 2)
    ff_use_modal_workers: bool = False
    ff_enable_llm_enrichment: bool = False
    ff_enforce_quotas: bool = True
    ff_show_fixture_data: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
