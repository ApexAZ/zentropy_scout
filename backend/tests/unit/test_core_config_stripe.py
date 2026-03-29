"""Tests for Stripe configuration settings.

REQ-029 §11: Stripe config vars, production security validation, and
configuration matrix (credits × metering) warning.
REQ-030 §9: Reservation config, production rejection of credits+!metering.
"""

import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings

# Reusable test constants
_SECURE_DB_PASSWORD = "my-secure-production-password-123!"
_PRODUCTION = "production"
_STRIPE_TEST_KEY = "sk_test_abc123"
_STRIPE_LIVE_KEY = "sk_live_abc123"  # gitleaks:allow (fake test key)
_STRIPE_WEBHOOK_SECRET = "whsec_valid"


class TestStripeConfigDefaults:
    """REQ-029 §11.2: Stripe settings have correct defaults."""

    def test_stripe_secret_key_defaults_to_empty(self):
        """Stripe secret key defaults to empty string (not required locally)."""
        s = Settings(_env_file=None)
        assert s.stripe_secret_key.get_secret_value() == ""

    def test_stripe_webhook_secret_defaults_to_empty(self):
        """Stripe webhook secret defaults to empty string."""
        s = Settings(_env_file=None)
        assert s.stripe_webhook_secret.get_secret_value() == ""

    def test_stripe_publishable_key_defaults_to_empty(self):
        """Stripe publishable key defaults to empty string."""
        s = Settings(_env_file=None)
        assert s.stripe_publishable_key == ""

    def test_credits_enabled_defaults_to_true(self):
        """Credits enabled defaults to true."""
        s = Settings(_env_file=None)
        assert s.credits_enabled is True

    def test_stripe_secret_key_is_secret_str(self):
        """Stripe secret key uses SecretStr for masking in logs."""
        s = Settings(stripe_secret_key=_STRIPE_TEST_KEY)
        assert _STRIPE_TEST_KEY not in repr(s)
        assert s.stripe_secret_key.get_secret_value() == _STRIPE_TEST_KEY

    def test_stripe_webhook_secret_is_secret_str(self):
        """Stripe webhook secret uses SecretStr for masking in logs."""
        s = Settings(stripe_webhook_secret="whsec_abc123")
        assert "whsec_abc123" not in repr(s)
        assert s.stripe_webhook_secret.get_secret_value() == "whsec_abc123"


class TestStripeConfigEnvLoading:
    """REQ-029 §11.1: Stripe settings loaded from environment variables."""

    def test_stripe_secret_key_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """STRIPE_SECRET_KEY env var is loaded into settings."""
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_from_env")
        s = Settings()
        assert s.stripe_secret_key.get_secret_value() == "sk_test_from_env"

    def test_stripe_webhook_secret_loaded_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """STRIPE_WEBHOOK_SECRET env var is loaded into settings."""
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_from_env")
        s = Settings()
        assert s.stripe_webhook_secret.get_secret_value() == "whsec_from_env"

    def test_stripe_publishable_key_loaded_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """STRIPE_PUBLISHABLE_KEY env var is loaded into settings."""
        monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_from_env")
        s = Settings()
        assert s.stripe_publishable_key == "pk_test_from_env"

    def test_credits_enabled_loaded_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """CREDITS_ENABLED env var is correctly parsed as boolean."""
        monkeypatch.setenv("CREDITS_ENABLED", "false")
        s = Settings()
        assert s.credits_enabled is False


class TestStripeProductionValidation:
    """REQ-029 §11.3: Production security checks for Stripe config."""

    def test_rejects_empty_stripe_secret_key_in_production_when_credits_enabled(
        self,
    ):
        """Stripe secret key required in production when credits enabled."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                credits_enabled=True,
                stripe_secret_key="",
                stripe_webhook_secret=_STRIPE_WEBHOOK_SECRET,
            )
        assert "STRIPE_SECRET_KEY required in production" in str(exc_info.value)

    def test_rejects_empty_stripe_webhook_secret_in_production_when_credits_enabled(
        self,
    ):
        """Stripe webhook secret required in production when credits enabled."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                credits_enabled=True,
                stripe_secret_key=_STRIPE_LIVE_KEY,
                stripe_webhook_secret="",
            )
        assert "STRIPE_WEBHOOK_SECRET required in production" in str(exc_info.value)

    def test_rejects_test_key_in_production(self):
        """sk_test_ prefix rejected in production (must use live keys)."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                credits_enabled=True,
                stripe_secret_key=_STRIPE_TEST_KEY,
                stripe_webhook_secret=_STRIPE_WEBHOOK_SECRET,
            )
        assert "must use live keys in production" in str(exc_info.value)

    def test_allows_live_key_in_production(self):
        """sk_live_ prefix accepted in production."""
        s = Settings(
            environment=_PRODUCTION,
            database_password=_SECURE_DB_PASSWORD,
            credits_enabled=True,
            stripe_secret_key=_STRIPE_LIVE_KEY,
            stripe_webhook_secret=_STRIPE_WEBHOOK_SECRET,
        )
        assert s.stripe_secret_key.get_secret_value() == _STRIPE_LIVE_KEY

    def test_allows_empty_stripe_keys_when_credits_disabled(self):
        """Stripe keys not required when credits are disabled."""
        s = Settings(
            environment=_PRODUCTION,
            database_password=_SECURE_DB_PASSWORD,
            credits_enabled=False,
            stripe_secret_key="",
            stripe_webhook_secret="",
        )
        assert s.credits_enabled is False

    def test_allows_test_key_in_development(self):
        """sk_test_ prefix is fine in development."""
        s = Settings(
            environment="development",
            credits_enabled=True,
            stripe_secret_key=_STRIPE_TEST_KEY,
            stripe_webhook_secret="whsec_test",
        )
        assert s.stripe_secret_key.get_secret_value() == _STRIPE_TEST_KEY


class TestStripeConfigMatrix:
    """REQ-029 §11.4 / REQ-021 §10.3: Configuration matrix validation."""

    def test_warns_credits_enabled_without_metering_non_production(self, caplog):
        """credits_enabled=True + metering_enabled=False logs warning in non-production."""
        with caplog.at_level(logging.WARNING):
            Settings(
                credits_enabled=True,
                metering_enabled=False,
                environment="development",
            )
        assert any(
            "credits_enabled=True" in record.message
            and "metering_enabled=False" in record.message
            for record in caplog.records
        )

    def test_rejects_credits_enabled_without_metering_production(self):
        """credits_enabled=True + metering_enabled=False raises ValueError in production."""
        with pytest.raises(
            ValidationError, match="credits_enabled=True requires metering"
        ):
            Settings(
                credits_enabled=True,
                metering_enabled=False,
                environment=_PRODUCTION,
                database_password=_SECURE_DB_PASSWORD,
                stripe_secret_key=_STRIPE_LIVE_KEY,
                stripe_webhook_secret=_STRIPE_WEBHOOK_SECRET,
            )

    def test_no_warning_when_both_disabled(self, caplog):
        """No warning when both credits and metering disabled."""
        with caplog.at_level(logging.WARNING):
            Settings(
                credits_enabled=False,
                metering_enabled=False,
            )
        assert not any("credits_enabled" in record.message for record in caplog.records)

    def test_no_warning_when_both_enabled(self, caplog):
        """No warning when both credits and metering enabled (production config)."""
        with caplog.at_level(logging.WARNING):
            Settings(
                credits_enabled=True,
                metering_enabled=True,
            )
        assert not any("credits_enabled" in record.message for record in caplog.records)


class TestReservationConfig:
    """REQ-030 §9.2: Reservation system configuration variables."""

    def test_reservation_ttl_defaults_to_300(self):
        """reservation_ttl_seconds defaults to 300."""
        s = Settings(_env_file=None)
        assert s.reservation_ttl_seconds == 300

    def test_reservation_sweep_interval_defaults_to_300(self):
        """reservation_sweep_interval_seconds defaults to 300."""
        s = Settings(_env_file=None)
        assert s.reservation_sweep_interval_seconds == 300

    def test_reservation_ttl_can_be_overridden(self):
        """reservation_ttl_seconds can be set via constructor."""
        s = Settings(reservation_ttl_seconds=600, _env_file=None)
        assert s.reservation_ttl_seconds == 600

    def test_reservation_sweep_interval_can_be_overridden(self):
        """reservation_sweep_interval_seconds can be set via constructor."""
        s = Settings(reservation_sweep_interval_seconds=120, _env_file=None)
        assert s.reservation_sweep_interval_seconds == 120
