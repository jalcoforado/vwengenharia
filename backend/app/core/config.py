from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "VW Engenharia"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://vw:vw@localhost:5432/vwengenharia"
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
