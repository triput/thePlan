from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://theplan:theplan@localhost:5432/theplan"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    bootstrap_user_id: str = "00000000-0000-0000-0000-000000000001"
    bootstrap_user_email: str = "local@localhost"
    bootstrap_user_display_name: str = "Local User"


@lru_cache
def get_settings() -> Settings:
    return Settings()
