"""Application configuration loaded from environment variables.

REQ-006 §6.1: Settings for database, API, LLM providers, and authentication.
Uses pydantic-settings for validation and .env file support.
"""

import uuid

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known insecure default password that must not be used in production
# Security: Runtime check in check_production_security() prevents use in production
_INSECURE_DEFAULT_PASSWORD = "zentropy_dev_password"  # nosec B105


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
    # 0.0.0.0 binds to all network interfaces (required for Docker containers)
    # Security: For local development without Docker, use 127.0.0.1 to prevent
    # external access. In production, use a reverse proxy with TLS termination.
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000

    # CORS (Security)
    # Default allows localhost:3000 for Next.js development
    # Production: Set ALLOWED_ORIGINS to specific domain(s)
    allowed_origins: list[str] = ["http://localhost:3000"]

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

    # Rate Limiting (Security)
    # Limits LLM-calling endpoints to prevent abuse and cost explosion
    # Format: "count/period" (e.g., "10/minute", "100/hour")
    rate_limit_llm: str = "10/minute"  # /ingest, /chat/messages
    rate_limit_embeddings: str = "5/minute"  # embedding regeneration
    rate_limit_enabled: bool = True  # Disable for testing

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

    @model_validator(mode="after")
    def check_production_security(self) -> "Settings":
        """Validate production security requirements.

        Security: Prevents deployment with known insecure defaults.
        """
        if (
            self.environment == "production"
            and self.database_password == _INSECURE_DEFAULT_PASSWORD
        ):
            msg = (
                "Cannot use default database password in production. "
                "Set DATABASE_PASSWORD environment variable to a secure value."
            )
            raise ValueError(msg)
        return self


settings = Settings()
