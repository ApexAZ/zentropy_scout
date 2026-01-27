"""Tests for provider error taxonomy (REQ-009 §7.1).

Tests behavior of error classes:
- Inheritance hierarchy
- Required attributes (e.g., retry_after_seconds)
- Error classification for retry logic
"""

import pytest

from app.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    TransientError,
)


class TestProviderErrorHierarchy:
    """Test error inheritance structure."""

    def test_provider_error_is_exception(self):
        """ProviderError should be a standard Exception."""
        error = ProviderError("test")
        assert isinstance(error, Exception)

    @pytest.mark.parametrize(
        "error_class",
        [
            RateLimitError,
            AuthenticationError,
            ModelNotFoundError,
            ContentFilterError,
            ContextLengthError,
            TransientError,
        ],
    )
    def test_all_errors_inherit_from_provider_error(self, error_class):
        """All provider errors should inherit from ProviderError."""
        error = error_class("test message")
        assert isinstance(error, ProviderError)

    @pytest.mark.parametrize(
        "error_class",
        [
            RateLimitError,
            AuthenticationError,
            ModelNotFoundError,
            ContentFilterError,
            ContextLengthError,
            TransientError,
        ],
    )
    def test_errors_preserve_message(self, error_class):
        """All errors should preserve their message."""
        error = error_class("specific error message")
        assert str(error) == "specific error message"


class TestRateLimitError:
    """Test RateLimitError specific behavior."""

    def test_has_retry_after_seconds_attribute(self):
        """RateLimitError should have retry_after_seconds attribute."""
        error = RateLimitError("rate limited", retry_after_seconds=30.0)
        assert error.retry_after_seconds == 30.0

    def test_retry_after_defaults_to_none(self):
        """retry_after_seconds should default to None when not provided."""
        error = RateLimitError("rate limited")
        assert error.retry_after_seconds is None

    def test_retry_after_accepts_float(self):
        """retry_after_seconds should accept float values."""
        error = RateLimitError("rate limited", retry_after_seconds=1.5)
        assert error.retry_after_seconds == 1.5


class TestRetryableErrors:
    """Test which errors are considered retryable."""

    def test_transient_error_is_retryable(self):
        """TransientError should be safe to retry."""
        error = TransientError("network timeout")
        # Retryable errors can be caught together
        assert isinstance(error, TransientError | RateLimitError)

    def test_rate_limit_error_is_retryable(self):
        """RateLimitError should be retryable (with delay)."""
        error = RateLimitError("too many requests")
        assert isinstance(error, TransientError | RateLimitError)

    def test_authentication_error_not_retryable(self):
        """AuthenticationError should not be retryable."""
        error = AuthenticationError("invalid key")
        assert not isinstance(error, TransientError | RateLimitError)

    def test_context_length_error_not_retryable(self):
        """ContextLengthError should not be retryable without modification."""
        error = ContextLengthError("input too long")
        assert not isinstance(error, TransientError | RateLimitError)
