import uuid

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "zentropy_scout"
    database_user: str = "zentropy_user"
    database_password: str = "zentropy_dev_password"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Authentication (REQ-006 §6.1)
    # Local-first mode: DEFAULT_USER_ID provides user context without token
    # Future hosted mode: auth_enabled=True, JWT/session token required
    default_user_id: uuid.UUID | None = None
    auth_enabled: bool = False

    @property
    def database_url(self) -> str:
        """Async database URL for SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )

    @property
    def database_url_sync(self) -> str:
        """Sync database URL for Alembic."""
        return (
            f"postgresql://{self.database_user}:{self.database_password}"
            f"@{self.database_host}:{self.database_port}/{self.database_name}"
        )


settings = Settings()
