"""Provider factory functions.

REQ-009 §6.3: Singleton pattern for provider instances.
"""

from app.providers.config import ProviderConfig
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.openai_adapter import OpenAIEmbeddingAdapter
from app.providers.llm.base import LLMProvider
from app.providers.llm.claude_adapter import ClaudeAdapter
from app.providers.llm.gemini_adapter import GeminiAdapter
from app.providers.llm.openai_adapter import OpenAIAdapter

_llm_provider: LLMProvider | None = None
_embedding_provider: EmbeddingProvider | None = None


def get_llm_provider(config: ProviderConfig | None = None) -> LLMProvider:
    """Get or create the LLM provider singleton.

    WHY SINGLETON:
    - Reuses HTTP connections (performance)
    - Centralized rate limiting
    - Consistent configuration across app

    WHY OPTIONAL CONFIG:
    - First call sets the config (app startup)
    - Subsequent calls reuse (business logic)

    Args:
        config: Optional provider configuration. If None and no provider
            exists, loads from environment.

    Returns:
        LLMProvider instance.

    Raises:
        ValueError: If the configured provider is unknown.
    """
    global _llm_provider

    if _llm_provider is None:
        if config is None:
            config = ProviderConfig.from_env()

        if config.llm_provider == "claude":
            _llm_provider = ClaudeAdapter(config)
        elif config.llm_provider == "openai":
            _llm_provider = OpenAIAdapter(config)
        elif config.llm_provider == "gemini":
            _llm_provider = GeminiAdapter(config)
        else:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider}")

    return _llm_provider


def get_embedding_provider(
    config: ProviderConfig | None = None,
) -> EmbeddingProvider:
    """Get or create the embedding provider singleton.

    Args:
        config: Optional provider configuration. If None and no provider
            exists, loads from environment.

    Returns:
        EmbeddingProvider instance.

    Raises:
        ValueError: If the configured provider is unknown.
    """
    global _embedding_provider

    if _embedding_provider is None:
        if config is None:
            config = ProviderConfig.from_env()

        if config.embedding_provider == "openai":
            _embedding_provider = OpenAIEmbeddingAdapter(config)
        elif config.embedding_provider == "cohere":
            # Cohere adapter will be added in future
            raise NotImplementedError("Cohere embedding adapter not yet implemented")
        else:
            raise ValueError(f"Unknown embedding provider: {config.embedding_provider}")

    return _embedding_provider


def reset_providers() -> None:
    """Reset provider singletons.

    Used in tests to ensure isolation between test cases.
    """
    global _llm_provider, _embedding_provider
    _llm_provider = None
    _embedding_provider = None
