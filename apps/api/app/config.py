from functools import lru_cache
import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SESSION_SECRET = "dev-insecure-session-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://theplan:theplan@localhost:5432/theplan"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    bootstrap_user_id: str = "00000000-0000-0000-0000-000000000001"
    bootstrap_user_email: str = "local@localhost"
    bootstrap_user_display_name: str = "Local User"
    session_secret: str = _DEV_SESSION_SECRET
    session_https_only: bool = False
    session_max_age_seconds: int = 1209600
    seed_demo_user: bool = True
    demo_nebula_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.session_secret == _DEV_SESSION_SECRET:
        warnings.warn(
            "Using default SESSION_SECRET; set SESSION_SECRET in production",
            stacklevel=2,
        )
    return settings
