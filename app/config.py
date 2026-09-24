from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ScribeAI"
    environment: str = "development"
    database_url: str | None = None
    redis_url: str | None = None
    translation_api_url: str = "https://api.openai.com/v1"
    translation_api_key: str | None = None
    translation_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:8000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
