"""
Application settings loaded from environment variables.

Uses pydantic-settings to read .env in development. In production
the same variables would come from the host environment instead.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────
    DB_USER: str = "hackathon"
    DB_PASSWORD: str = "hackathon"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "blocket_smart"

    # ── OpenAI ───────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    # gpt-4o-mini is the budget option: cheap, fast, plenty for
    # listing analysis and search summaries. Bump to gpt-4o only
    # if a specific feature actually needs it.
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Blocket ──────────────────────────────────────────────────
    # Optional. Only needed if we use endpoints that require auth
    # (saved searches / "Bevakningar"). Public search works without.
    BLOCKET_BEARER_TOKEN: str = ""

    # ── App behaviour ────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # How often the sync worker polls Blocket (seconds)
    SYNC_INTERVAL_SECONDS: int = 30

    # Demo mode: when true, the API serves cached data instead of
    # hitting Blocket live. Useful during the actual demo so we
    # never get rate-limited mid-presentation.
    DEMO_MODE: bool = False

    @property
    def DATABASE_URL(self) -> str:
        """SQLAlchemy connection string using psycopg v3 driver."""
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # don't crash on unknown vars in .env
    )


# Single shared instance used throughout the app
settings = Settings()