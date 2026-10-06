from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "VW Engenharia"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://vw:vw@localhost:5432/vwengenharia"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "development-only-change-me-use-32-bytes-minimum"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "vwengenharia"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "development-only-change-me"
    s3_region: str = "us-east-1"
    s3_presign_seconds: int = 900

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env.lower() in {"production", "prod"} and self.jwt_secret == (
            "development-only-change-me-use-32-bytes-minimum"
        ):
            raise ValueError("JWT_SECRET must be configured in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
