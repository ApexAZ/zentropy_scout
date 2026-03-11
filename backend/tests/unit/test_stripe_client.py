"""Tests for StripeClient factory and dependency injection.

REQ-029 §5.2: StripeClient configuration with API version pinning.
"""

from unittest.mock import MagicMock, patch

from app.core.stripe_client import STRIPE_API_VERSION, get_stripe_client

_SETTINGS_PATH = "app.core.stripe_client.settings"
_CLIENT_PATH = "app.core.stripe_client.StripeClient"


class TestStripeClientFactory:
    """REQ-029 §5.2: StripeClient factory creates correctly configured clients."""

    def _mock_settings(self) -> MagicMock:
        """Create mock settings with a test Stripe secret key."""
        mock = MagicMock()
        mock.stripe_secret_key.get_secret_value.return_value = "sk_test_factory"
        return mock

    def test_passes_api_key_from_settings(self):
        """Factory reads stripe_secret_key and passes it to StripeClient."""
        mock_settings = self._mock_settings()

        with patch(_SETTINGS_PATH, mock_settings), patch(_CLIENT_PATH) as mock_cls:
            get_stripe_client()

        assert mock_cls.call_args.kwargs["api_key"] == "sk_test_factory"

    def test_pins_api_version(self):
        """API version is pinned to prevent surprise breaking changes."""
        mock_settings = self._mock_settings()

        with patch(_SETTINGS_PATH, mock_settings), patch(_CLIENT_PATH) as mock_cls:
            get_stripe_client()

        assert mock_cls.call_args.kwargs["stripe_version"] == STRIPE_API_VERSION

    def test_unwraps_secret_str(self):
        """Factory calls get_secret_value() — never passes SecretStr object."""
        mock_settings = self._mock_settings()

        with patch(_SETTINGS_PATH, mock_settings), patch(_CLIENT_PATH):
            get_stripe_client()

        mock_settings.stripe_secret_key.get_secret_value.assert_called_once()
