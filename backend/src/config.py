from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root is two levels up from this file: src/config.py → src/ → backend/ → root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────
    DB_USER: str = "hackathon"
    DB_PASSWORD: str = "hackathon"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "blocket_smart"

    # ── OpenAI ───────────────────────────────────────────────────
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "qwen3:14b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    EMBEDDING_DIMENSIONS: int = 768

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

    @property
    def ai_base_url(self) -> str | None:
        return self.OPENAI_BASE_URL or self.AI_BASE_URL or None

    @property
    def ai_api_key(self) -> str:
        return self.OPENAI_API_KEY or self.AI_API_KEY or "ollama"

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),         # absolut path till .env
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
