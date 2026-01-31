"""Tests for application configuration.

Security: Tests for production security validation.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestProductionSecurityValidation:
    """Tests for production security requirements."""

    def test_allows_default_password_in_development(self):
        """Default password is allowed in development environment."""
        # This should not raise
        settings = Settings(
            environment="development",
            database_password="zentropy_dev_password",
        )
        assert settings.database_password == "zentropy_dev_password"

    def test_rejects_default_password_in_production(self):
        """Default password is rejected in production environment."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="production",
                database_password="zentropy_dev_password",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Cannot use default database password in production" in str(
            errors[0]["msg"]
        )

    def test_allows_custom_password_in_production(self):
        """Custom password is allowed in production environment."""
        settings = Settings(
            environment="production",
            database_password="my-secure-production-password-123!",
        )
        assert settings.database_password == "my-secure-production-password-123!"

    def test_allows_default_password_in_staging(self):
        """Default password is allowed in non-production environments."""
        # Staging, test, etc. are not blocked
        settings = Settings(
            environment="staging",
            database_password="zentropy_dev_password",
        )
        assert settings.environment == "staging"
