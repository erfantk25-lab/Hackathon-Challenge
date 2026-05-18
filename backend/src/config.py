from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────
    DB_USER: str = "hackathon_user"
    DB_PASSWORD: str = "hackathon_password"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5433
    DB_NAME: str = "hackathon_db"

    # ── OpenAI (used for LLM analysis only, not embeddings) ──────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Blocket ──────────────────────────────────────────────────
    BLOCKET_BEARER_TOKEN: str = ""

    # ── App behaviour ────────────────────────────────────────────
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    SYNC_INTERVAL_SECONDS: int = 30
    DEMO_MODE: bool = False

    @property
    def DATABASE_URL(self) -> str:
        """SQLAlchemy connection string using psycopg v3 driver."""
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
