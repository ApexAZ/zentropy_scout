"""Provider abstraction layer.

Exports:
    Error classes for provider error handling
    ProviderConfig for configuration
    Factory functions for provider instances
"""

from app.providers.config import ProviderConfig
from app.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    ModelNotFoundError,
    ProviderError,
    RateLimitError,
    TransientError,
)
from app.providers.factory import (
    get_embedding_provider,
    get_llm_provider,
    get_llm_registry,
)

__all__ = [
    # Config
    "ProviderConfig",
    # Errors
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "ModelNotFoundError",
    "ContentFilterError",
    "ContextLengthError",
    "TransientError",
    # Factory
    "get_llm_provider",
    "get_llm_registry",
    "get_embedding_provider",
]
