"""Provider error taxonomy.

REQ-009 §7.1: Error classes for provider abstraction layer.

WHY SEPARATE ERROR CLASSES:
- Enables callers to handle errors differently based on type
- Clear distinction between retryable and non-retryable errors
- Provider-agnostic error handling (adapters map to these)
"""


__all__ = [
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
    "ContentFilterError",
    "ContextLengthError",
    "TransientError",
]


class ProviderError(Exception):
    """Base class for all provider errors.

    All provider-specific exceptions should inherit from this class,
    allowing callers to catch all provider errors with a single handler.
    """

    pass


class RateLimitError(ProviderError):
    """Rate limit exceeded.

    WHY SEPARATE FROM TRANSIENT:
    - May have specific retry_after_seconds hint from provider
    - Callers may want to queue rather than immediately retry
    """

    def __init__(self, message: str, retry_after_seconds: float | None = None):
        """Initialize RateLimitError.

        Args:
            message: Error description from the provider.
            retry_after_seconds: Optional hint from provider on when to retry.
        """
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class AuthenticationError(ProviderError):
    """Invalid or expired API key.

    WHY NOT RETRYABLE:
    - Requires user intervention (new API key)
    - Retrying will just waste quota/time
    """

    pass


class ModelNotFoundError(ProviderError):
    """Requested model doesn't exist or isn't accessible.

    WHY SEPARATE:
    - Clear indication of configuration issue
    - Different from auth errors (key is valid, model isn't)
    """

    pass


class ContentFilterError(ProviderError):
    """Content blocked by provider's safety filter.

    WHY SEPARATE:
    - May need prompt modification, not just retry
    - Useful for logging/debugging content issues
    """

    pass


class ContextLengthError(ProviderError):
    """Input exceeded model's context window.

    WHY SEPARATE:
    - Need to truncate/summarize, not retry
    - Common issue with long job descriptions or resumes
    """

    pass


class TransientError(ProviderError):
    """Temporary failure (network, server overload).

    WHY SEPARATE:
    - Safe to retry with exponential backoff
    - Includes: connection errors, timeouts, 5xx responses
    """

    pass
