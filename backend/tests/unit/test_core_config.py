"""Tests for application configuration.

REQ-006 §6.1, REQ-013 §7.2, §11: Settings for database, API, LLM providers,
and authentication. Tests cover defaults, env var loading, and production
security validation.
"""

import pytest
from pydantic import ValidationError

from app.core.config import _INSECURE_DEFAULT_PASSWORD, Settings

# Reusable test constants
_SECURE_DB_PASSWORD = "my-secure-production-password-123!"
_TEST_AUTH_SECRET = "a" * 64
_PRODUCTION = "production"


class TestProductionSecurityValidation:
    """Tests for production security requirements."""

    def test_allows_default_password_in_development(self):
        """Default password is allowed in development environment."""
        s = Settings(
            environment="development",
            database_password=_INSECURE_DEFAULT_PASSWORD,
        )
        assert s.database_password == _INSECURE_DEFAULT_PASSWORD

    def test_rejects_default_password_in_production(self):
        """Default password is rejected in production environment."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_INSECURE_DEFAULT_PASSWORD,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "Cannot use default database password in production" in str(
            errors[0]["msg"]
        )

    def test_allows_custom_password_in_production(self):
        """Custom password is allowed in production environment."""
        s = Settings(
            environment=_PRODUCTION,
            database_password=_SECURE_DB_PASSWORD,
        )
        assert s.database_password == _SECURE_DB_PASSWORD

    def test_allows_default_password_in_staging(self):
        """Default password is allowed in non-production environments."""
        s = Settings(
            environment="staging",
            database_password=_INSECURE_DEFAULT_PASSWORD,
        )
        assert s.environment == "staging"


class TestAuthConfigDefaults:
    """REQ-013 §7.2: Auth settings have correct defaults."""

    def test_auth_enabled_defaults_to_false(self):
        """Auth is disabled by default for local development."""
        s = Settings()
        assert s.auth_enabled is False

    def test_auth_secret_defaults_to_empty(self):
        """Auth secret is empty by default (not required in local mode)."""
        s = Settings()
        assert s.auth_secret.get_secret_value() == ""

    def test_auth_issuer_defaults_to_zentropy_scout(self):
        """JWT issuer claim defaults to 'zentropy-scout'."""
        s = Settings()
        assert s.auth_issuer == "zentropy-scout"

    def test_auth_cookie_name_defaults_to_zentropy_session_token(self):
        """Cookie name defaults to 'zentropy.session-token'."""
        s = Settings()
        assert s.auth_cookie_name == "zentropy.session-token"

    def test_auth_cookie_secure_defaults_to_true(self):
        """Cookie Secure flag defaults to True (HTTPS only)."""
        s = Settings()
        assert s.auth_cookie_secure is True

    def test_auth_cookie_samesite_defaults_to_lax(self):
        """Cookie SameSite defaults to 'lax' (CSRF protection)."""
        s = Settings()
        assert s.auth_cookie_samesite == "lax"

    def test_auth_cookie_domain_defaults_to_empty_string(self):
        """Cookie domain defaults to empty (request origin)."""
        s = Settings()
        assert s.auth_cookie_domain == ""

    def test_default_user_id_defaults_to_none(self):
        """Default user ID is None when not set."""
        s = Settings()
        assert s.default_user_id is None


class TestOAuthAndEmailDefaults:
    """REQ-013 §7.2, §11: OAuth and email settings have correct defaults."""

    def test_google_client_id_defaults_to_empty(self):
        """Google OAuth client ID defaults to empty."""
        s = Settings()
        assert s.google_client_id == ""

    def test_google_client_secret_defaults_to_empty(self):
        """Google OAuth client secret defaults to empty (SecretStr)."""
        s = Settings()
        assert s.google_client_secret.get_secret_value() == ""

    def test_linkedin_client_id_defaults_to_empty(self):
        """LinkedIn OAuth client ID defaults to empty."""
        s = Settings()
        assert s.linkedin_client_id == ""

    def test_linkedin_client_secret_defaults_to_empty(self):
        """LinkedIn OAuth client secret defaults to empty (SecretStr)."""
        s = Settings()
        assert s.linkedin_client_secret.get_secret_value() == ""

    def test_email_from_defaults_to_noreply(self):
        """Email sender defaults to noreply@zentropyscout.com."""
        s = Settings()
        assert s.email_from == "noreply@zentropyscout.com"

    def test_resend_api_key_defaults_to_empty(self):
        """Resend API key defaults to empty (SecretStr)."""
        s = Settings()
        assert s.resend_api_key.get_secret_value() == ""

    def test_frontend_url_defaults_to_localhost(self):
        """Frontend URL defaults to http://localhost:3000."""
        s = Settings()
        assert s.frontend_url == "http://localhost:3000"


class TestAuthProductionValidation:
    """REQ-013 §7.2: Production validation for auth settings."""

    def test_rejects_empty_auth_secret_in_production_when_auth_enabled(self):
        """Auth secret must be set when auth is enabled in production."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                auth_enabled=True,
                auth_secret="",
            )
        assert "AUTH_SECRET must be set" in str(exc_info.value)

    def test_rejects_short_auth_secret_in_production_when_auth_enabled(self):
        """Auth secret must be >= 32 characters in production."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                auth_enabled=True,
                auth_secret="too-short",
            )
        assert "AUTH_SECRET must be at least 32 characters" in str(exc_info.value)

    def test_rejects_auth_secret_at_boundary_minus_one(self):
        """Auth secret of exactly 31 chars is rejected in production."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                auth_enabled=True,
                auth_secret="a" * 31,
            )
        assert "AUTH_SECRET must be at least 32 characters" in str(exc_info.value)

    def test_allows_auth_secret_at_exact_boundary(self):
        """Auth secret of exactly 32 chars is accepted in production."""
        s = Settings(
            environment=_PRODUCTION,
            database_password=_SECURE_DB_PASSWORD,
            auth_enabled=True,
            auth_secret="a" * 32,
        )
        assert len(s.auth_secret.get_secret_value()) == 32

    def test_allows_empty_auth_secret_when_auth_disabled(self):
        """Auth secret not required when auth is disabled."""
        s = Settings(
            environment=_PRODUCTION,
            database_password=_SECURE_DB_PASSWORD,
            auth_enabled=False,
            auth_secret="",
        )
        assert s.auth_secret.get_secret_value() == ""

    def test_allows_empty_auth_secret_in_development_with_auth_enabled(self):
        """Auth secret not required in development even with auth enabled."""
        s = Settings(auth_enabled=True, auth_secret="")
        assert s.auth_secret.get_secret_value() == ""

    def test_allows_valid_auth_secret_in_production(self):
        """Valid auth secret (>= 32 chars) accepted in production."""
        s = Settings(
            environment=_PRODUCTION,
            database_password=_SECURE_DB_PASSWORD,
            auth_enabled=True,
            auth_secret=_TEST_AUTH_SECRET,
        )
        assert s.auth_secret.get_secret_value() == _TEST_AUTH_SECRET


class TestAuthCookieSameSiteValidation:
    """REQ-013 §10.1: Cookie SameSite must be a valid value."""

    def test_accepts_lax(self):
        """SameSite 'lax' is valid."""
        s = Settings(auth_cookie_samesite="lax")
        assert s.auth_cookie_samesite == "lax"

    def test_accepts_strict(self):
        """SameSite 'strict' is valid."""
        s = Settings(auth_cookie_samesite="strict")
        assert s.auth_cookie_samesite == "strict"

    def test_accepts_none_with_secure(self):
        """SameSite 'none' is valid when Secure is true."""
        s = Settings(auth_cookie_samesite="none", auth_cookie_secure=True)
        assert s.auth_cookie_samesite == "none"

    def test_rejects_invalid_value(self):
        """SameSite rejects invalid values."""
        with pytest.raises(ValidationError):
            Settings(auth_cookie_samesite="invalid")

    def test_rejects_none_without_secure(self):
        """SameSite 'none' requires Secure flag (browser requirement)."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(auth_cookie_samesite="none", auth_cookie_secure=False)
        assert "AUTH_COOKIE_SECURE must be true" in str(exc_info.value)


class TestCorsWildcardValidation:
    """REQ-013 §7.6: CORS wildcard incompatible with credentials."""

    def test_rejects_wildcard_origin(self):
        """Wildcard origin is rejected (incompatible with credentials)."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(allowed_origins=["*"])
        assert "must not contain '*'" in str(exc_info.value)

    def test_allows_specific_origins(self):
        """Specific origins are accepted."""
        s = Settings(allowed_origins=["http://localhost:3000"])
        assert s.allowed_origins == ["http://localhost:3000"]


class TestAuthConfigEnvLoading:
    """REQ-013 §11: Auth settings loaded from environment variables."""

    def test_auth_secret_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """AUTH_SECRET env var is loaded into settings."""
        monkeypatch.setenv("AUTH_SECRET", "my-secret-key-for-testing-purposes-long")
        s = Settings()
        assert (
            s.auth_secret.get_secret_value()
            == "my-secret-key-for-testing-purposes-long"
        )

    def test_auth_enabled_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """AUTH_ENABLED env var is correctly parsed as boolean."""
        monkeypatch.setenv("AUTH_ENABLED", "true")
        s = Settings()
        assert s.auth_enabled is True

    def test_auth_cookie_secure_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """AUTH_COOKIE_SECURE env var is correctly parsed as boolean."""
        monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")
        s = Settings()
        assert s.auth_cookie_secure is False

    def test_auth_cookie_name_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """AUTH_COOKIE_NAME env var is loaded into settings."""
        monkeypatch.setenv("AUTH_COOKIE_NAME", "custom-cookie")
        s = Settings()
        assert s.auth_cookie_name == "custom-cookie"

    def test_frontend_url_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """FRONTEND_URL env var is loaded into settings."""
        monkeypatch.setenv("FRONTEND_URL", "https://app.zentropyscout.com")
        s = Settings()
        assert s.frontend_url == "https://app.zentropyscout.com"

    def test_google_client_id_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """GOOGLE_CLIENT_ID env var is loaded into settings."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "google-id-123")
        s = Settings()
        assert s.google_client_id == "google-id-123"

    def test_resend_api_key_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """RESEND_API_KEY env var is loaded into settings."""
        monkeypatch.setenv("RESEND_API_KEY", "re_test123")
        s = Settings()
        assert s.resend_api_key.get_secret_value() == "re_test123"
