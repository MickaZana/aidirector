from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

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

    anthropic_api_key: str = ""
    deepgram_api_key: str = ""

    sentry_dsn: str = ""
    logfire_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
