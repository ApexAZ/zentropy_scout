"""Shared Gemini error classification.

Maps Gemini SDK exceptions to the internal error taxonomy.
Used by both the Gemini LLM adapter and Gemini embedding adapter.

Coordinates with:
  - providers/errors.py (AuthenticationError, ContentFilterError,
    ContextLengthError, ProviderError, RateLimitError, TransientError)

Called by:
  - providers/llm/gemini_adapter.py (classify_gemini_error)
  - providers/embedding/gemini_adapter.py (classify_gemini_error)
"""

from app.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
    TransientError,
)


def classify_gemini_error(error: Exception) -> ProviderError:
    """Map Gemini exceptions to internal error taxonomy.

    Args:
        error: The exception raised by the Gemini SDK.

    Returns:
        Classified ProviderError subclass instance.
    """
    error_message = str(error)
    error_msg = error_message.lower()
    if "resource" in error_msg and "exhausted" in error_msg:
        return RateLimitError(error_message)
    if "permission" in error_msg or "unauthenticated" in error_msg:
        return AuthenticationError(error_message)
    if "context" in error_msg or "token" in error_msg:
        return ContextLengthError(error_message)
    if "safety" in error_msg or "blocked" in error_msg:
        return ContentFilterError(error_message)
    if "unavailable" in error_msg or "503" in error_msg:
        return TransientError(error_message)
    return ProviderError(error_message)
