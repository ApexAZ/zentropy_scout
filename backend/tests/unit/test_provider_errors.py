"""Tests for provider error taxonomy (REQ-009 §7.1).

Tests behavior of error classes:
- Message preservation across all error types
- RateLimitError retry_after_seconds behavior
"""

import pytest

from app.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    ModelNotFoundError,
    RateLimitError,
    TransientError,
)


class TestProviderErrorHierarchy:
    """Test error message preservation."""

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

    def test_retry_after_defaults_to_none(self):
        """retry_after_seconds should default to None when not provided."""
        error = RateLimitError("rate limited")
        assert error.retry_after_seconds is None

    def test_retry_after_accepts_float(self):
        """retry_after_seconds should accept float values."""
        error = RateLimitError("rate limited", retry_after_seconds=1.5)
        assert error.retry_after_seconds == 1.5
