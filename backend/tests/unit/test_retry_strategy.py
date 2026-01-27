"""Tests for provider retry strategy (REQ-009 §7.2).

Tests behavior of retry logic:
- Exponential backoff with jitter
- Rate limit retry_after_seconds handling
- Non-retryable errors fail immediately
- Max retries enforcement
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.providers.config import ProviderConfig
from app.providers.errors import (
    AuthenticationError,
    RateLimitError,
    TransientError,
)
from app.providers.retry import with_retries


@pytest.fixture
def config():
    """Provider config with test retry settings."""
    return ProviderConfig(
        max_retries=3,
        retry_base_delay_ms=100,  # Fast for tests
        retry_max_delay_ms=1000,
    )


class TestWithRetriesSuccess:
    """Test successful execution paths."""

    @pytest.mark.asyncio
    async def test_returns_result_on_success(self, config):
        """Should return function result when no error occurs."""
        func = AsyncMock(return_value="success")

        result = await with_retries(func, config)

        assert result == "success"
        func.assert_called_once()

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_error(self, config):
        """Should retry and succeed after transient error."""
        func = AsyncMock(side_effect=[TransientError("temporary"), "success"])

        with patch("app.providers.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await with_retries(func, config)

        assert result == "success"
        assert func.call_count == 2

    @pytest.mark.asyncio
    async def test_succeeds_after_rate_limit_error(self, config):
        """Should retry and succeed after rate limit error."""
        func = AsyncMock(side_effect=[RateLimitError("rate limited"), "success"])

        with patch("app.providers.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await with_retries(func, config)

        assert result == "success"
        assert func.call_count == 2


class TestWithRetriesFailure:
    """Test failure paths."""

    @pytest.mark.asyncio
    async def test_raises_after_max_retries_exceeded(self, config):
        """Should raise original error after max retries."""
        error = TransientError("persistent failure")
        func = AsyncMock(side_effect=error)

        with (
            patch("app.providers.retry.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(TransientError, match="persistent failure"),
        ):
            await with_retries(func, config)

        # Initial attempt + 3 retries = 4 total calls
        assert func.call_count == 4

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self, config):
        """Non-retryable errors should not trigger retry."""
        func = AsyncMock(side_effect=AuthenticationError("invalid key"))

        with pytest.raises(AuthenticationError, match="invalid key"):
            await with_retries(func, config)

        # Should fail immediately without retry
        func.assert_called_once()


class TestExponentialBackoff:
    """Test exponential backoff delay calculation."""

    @pytest.mark.asyncio
    async def test_delays_increase_exponentially(self, config):
        """Delays should double with each retry attempt."""
        func = AsyncMock(
            side_effect=[
                TransientError("fail 1"),
                TransientError("fail 2"),
                TransientError("fail 3"),
                "success",
            ]
        )
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with (
            patch("app.providers.retry.asyncio.sleep", side_effect=mock_sleep),
            patch("app.providers.retry.random.uniform", return_value=0),
        ):
            result = await with_retries(func, config)

        assert result == "success"
        # Base 100ms: delays should be ~0.1s, ~0.2s, ~0.4s (exponential)
        assert len(sleep_calls) == 3
        assert 0.08 <= sleep_calls[0] <= 0.12  # ~100ms
        assert 0.18 <= sleep_calls[1] <= 0.22  # ~200ms
        assert 0.38 <= sleep_calls[2] <= 0.42  # ~400ms

    @pytest.mark.asyncio
    async def test_delay_capped_at_max(self):
        """Delays should not exceed retry_max_delay_ms."""
        config = ProviderConfig(
            max_retries=5,
            retry_base_delay_ms=10000,  # 10 seconds base
            retry_max_delay_ms=15000,  # 15 second cap
        )
        func = AsyncMock(
            side_effect=[
                TransientError("fail"),
                TransientError("fail"),
                "success",
            ]
        )
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with (
            patch("app.providers.retry.asyncio.sleep", side_effect=mock_sleep),
            patch("app.providers.retry.random.uniform", return_value=0),
        ):
            await with_retries(func, config)

        # Second delay would be 20s without cap, but should be capped at 15s
        assert sleep_calls[1] <= 15.0


class TestRateLimitRetryAfter:
    """Test rate limit retry_after_seconds handling."""

    @pytest.mark.asyncio
    async def test_uses_retry_after_when_provided(self, config):
        """Should use retry_after_seconds from RateLimitError."""
        func = AsyncMock(
            side_effect=[
                RateLimitError("rate limited", retry_after_seconds=5.0),
                "success",
            ]
        )
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("app.providers.retry.asyncio.sleep", side_effect=mock_sleep):
            result = await with_retries(func, config)

        assert result == "success"
        # Should use the 5.0 second retry_after, not exponential backoff
        assert sleep_calls[0] == 5.0

    @pytest.mark.asyncio
    async def test_uses_backoff_when_retry_after_not_provided(self, config):
        """Should use exponential backoff when retry_after_seconds is None."""
        func = AsyncMock(
            side_effect=[
                RateLimitError("rate limited"),  # No retry_after_seconds
                "success",
            ]
        )
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with (
            patch("app.providers.retry.asyncio.sleep", side_effect=mock_sleep),
            patch("app.providers.retry.random.uniform", return_value=0),
        ):
            result = await with_retries(func, config)

        assert result == "success"
        # Should use exponential backoff (~100ms for first retry)
        assert 0.08 <= sleep_calls[0] <= 0.12


class TestCustomRetryableErrors:
    """Test custom retryable error configuration."""

    @pytest.mark.asyncio
    async def test_custom_retryable_errors(self, config):
        """Should retry only specified error types."""
        func = AsyncMock(side_effect=[TransientError("fail"), "success"])

        # Only retry TransientError, not RateLimitError
        with patch("app.providers.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await with_retries(
                func, config, retryable_errors=(TransientError,)
            )

        assert result == "success"
        assert func.call_count == 2
