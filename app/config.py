from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Risk Scoring Platform"
    app_version: str = "0.3.0"
    model_path: str = "app/models/risk_model.joblib"
    model_version: str = "v0.2.0"

    database_url: str = "postgresql+psycopg://risk:changeme@localhost:55432/risk_scoring"
    db_pool_size: int = 5
    db_max_overflow: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
