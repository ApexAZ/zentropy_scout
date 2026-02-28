"""Application configuration loaded from environment variables.

REQ-006 §6.1, REQ-013 §7.2, §11: Settings for database, API, LLM providers,
and authentication. Uses pydantic-settings for validation and .env file support.
"""

import uuid
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Known insecure default password that must not be used in production
# Security: Runtime check in check_production_security() prevents use in production
_INSECURE_DEFAULT_PASSWORD = "zentropy_dev_password"  # nosec B105

# Minimum length for AUTH_SECRET in production (256 bits = 32 bytes)
_MIN_AUTH_SECRET_LENGTH = 32


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
    database_password: str = _INSECURE_DEFAULT_PASSWORD

    # API
    # 0.0.0.0 binds to all network interfaces (required for Docker containers)
    # Security: For local development without Docker, use 127.0.0.1 to prevent
    # external access. In production, use a reverse proxy with TLS termination.
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000

    # CORS (Security)
    # Default allows localhost:3000 for Next.js development
    # Production: Set ALLOWED_ORIGINS to specific domain(s)
    # CRITICAL: Never set to ["*"] when allow_credentials=True (REQ-013 §7.6)
    allowed_origins: list[str] = ["http://localhost:3000"]

    # LLM Providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Application
    environment: str = "development"
    log_level: str = "INFO"

    # Authentication (REQ-013 §7.2)
    # Local-first mode: DEFAULT_USER_ID provides user context without JWT
    # Hosted mode: auth_enabled=True, JWT cookie required on every request
    default_user_id: uuid.UUID | None = None
    auth_enabled: bool = False
    auth_secret: SecretStr = SecretStr("")
    auth_issuer: str = "zentropy-scout"
    auth_cookie_name: str = "zentropy.session-token"
    auth_cookie_secure: bool = True
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_cookie_domain: str = ""

    # OAuth Providers (REQ-013 §4.1–§4.2)
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    linkedin_client_id: str = ""
    linkedin_client_secret: SecretStr = SecretStr("")

    # Email (REQ-013 §4.4)
    email_from: str = "noreply@zentropyscout.com"
    resend_api_key: SecretStr = SecretStr("")

    # Frontend URL (for OAuth redirect back to frontend)
    frontend_url: str = "http://localhost:3000"

    # Backend URL (for magic link emails that must hit the API directly)
    backend_url: str = "http://localhost:8000"

    # Resume Parsing (REQ-019 §9)
    resume_parse_max_size_mb: int = 10  # Maximum PDF upload size in MB

    # Metering (REQ-020 §11)
    metering_enabled: bool = True
    metering_margin_multiplier: float = 1.30
    metering_minimum_balance: float = 0.00

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
        Checks:
        - Metering margin must be positive (all environments)
        - Metering minimum balance must be non-negative (all environments)
        - Database password must not be the default in production
        - AUTH_SECRET must be set and >= 32 chars when auth is enabled in production
        - CORS must not use wildcard origin (incompatible with credentials)
        - SameSite=None requires Secure flag (browser requirement)
        """
        # Cookie security invariant: SameSite=None requires Secure (all environments)
        if self.auth_cookie_samesite == "none" and not self.auth_cookie_secure:
            msg = (
                "AUTH_COOKIE_SECURE must be true when AUTH_COOKIE_SAMESITE=none. "
                "Browsers reject SameSite=None cookies without the Secure flag."
            )
            raise ValueError(msg)

        # Metering config invariants (all environments)
        if self.metering_margin_multiplier <= 0:
            msg = (
                "METERING_MARGIN_MULTIPLIER must be positive. "
                f"Got: {self.metering_margin_multiplier}"
            )
            raise ValueError(msg)
        if self.metering_minimum_balance < 0:
            msg = (
                "METERING_MINIMUM_BALANCE cannot be negative. "
                f"Got: {self.metering_minimum_balance}"
            )
            raise ValueError(msg)

        # CORS wildcard with credentials is invalid (all environments)
        if "*" in self.allowed_origins:
            msg = (
                "ALLOWED_ORIGINS must not contain '*' (wildcard). "
                "This application uses credentials (cookies) which are "
                "incompatible with wildcard CORS origins."
            )
            raise ValueError(msg)

        if self.environment == "production":
            if self.database_password == _INSECURE_DEFAULT_PASSWORD:
                msg = (
                    "Cannot use default database password in production. "
                    "Set DATABASE_PASSWORD environment variable to a secure value."
                )
                raise ValueError(msg)

            if self.auth_enabled:
                secret_value = self.auth_secret.get_secret_value()
                if not secret_value:
                    msg = (
                        "AUTH_SECRET must be set when AUTH_ENABLED=true in production. "
                        'Generate with: python -c "import secrets; '
                        'print(secrets.token_hex(32))"'
                    )
                    raise ValueError(msg)
                if len(secret_value) < _MIN_AUTH_SECRET_LENGTH:
                    msg = (
                        f"AUTH_SECRET must be at least {_MIN_AUTH_SECRET_LENGTH} "
                        "characters for adequate security."
                    )
                    raise ValueError(msg)

        return self


settings = Settings()
