"""Retry strategy for provider operations.

REQ-009 §7.2: Exponential backoff with jitter for transient errors.

WHY EXPONENTIAL BACKOFF:
- Prevents thundering herd on recovery
- Respects provider rate limits
- Industry standard pattern

WHY JITTER:
- Prevents synchronized retries from multiple clients
- Spreads load more evenly
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeVar

from app.providers.errors import RateLimitError, TransientError

__all__ = ["with_retries"]

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_retries(
    func: Callable[[], Awaitable[T]],
    config: "ProviderConfig",
    retryable_errors: tuple[type[Exception], ...] = (TransientError, RateLimitError),
) -> T:
    """Execute function with exponential backoff retry.

    Args:
        func: Async function to execute (no arguments).
        config: Provider configuration with retry settings.
        retryable_errors: Tuple of error types that should trigger retry.

    Returns:
        Result from successful function execution.

    Raises:
        TransientError: If all retries exhausted due to transient failures.
        RateLimitError: If all retries exhausted due to rate limiting.
        RuntimeError: If retry loop exits unexpectedly without error or result.

    Note:
        If the error is a RateLimitError with retry_after_seconds set,
        that value is used instead of exponential backoff.
    """
    last_error: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func()
        except retryable_errors as e:
            last_error = e

            if attempt == config.max_retries:
                break  # No more retries

            # Calculate delay
            if isinstance(e, RateLimitError) and e.retry_after_seconds:
                delay = e.retry_after_seconds
            else:
                # Exponential backoff with jitter
                base_delay = config.retry_base_delay_ms * (2**attempt)
                jitter = random.uniform(0, base_delay * 0.1)
                delay = min(base_delay + jitter, config.retry_max_delay_ms) / 1000

            logger.warning(
                "Provider error (attempt %d/%d): %s. Retrying in %.2fs",
                attempt + 1,
                config.max_retries + 1,
                e,
                delay,
            )

            await asyncio.sleep(delay)

    # Should not reach here without an error, but satisfy type checker
    if last_error is not None:
        raise last_error
    raise RuntimeError("Retry loop exited without error or result")
