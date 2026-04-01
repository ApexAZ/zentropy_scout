"""Provider factory functions.

REQ-009 §6.3: Singleton pattern for provider instances.
REQ-028 §3: Registry factory for cross-provider dispatch.

Coordinates with:
  - providers/config.py (ProviderConfig)
  - providers/embedding/base.py (EmbeddingProvider)
  - providers/embedding/gemini_adapter.py (GeminiEmbeddingAdapter)
  - providers/embedding/openai_adapter.py (OpenAIEmbeddingAdapter)
  - providers/llm/base.py (LLMProvider)
  - providers/llm/claude_adapter.py (ClaudeAdapter)
  - providers/llm/gemini_adapter.py (GeminiAdapter)
  - providers/llm/openai_adapter.py (OpenAIAdapter)

Called by:
  - api/deps.py (get_llm_provider, get_llm_registry,
    get_embedding_provider)
  - services/generation/content_utils.py (get_llm_provider)
"""

from app.providers.config import ProviderConfig
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.gemini_adapter import GeminiEmbeddingAdapter
from app.providers.embedding.openai_adapter import OpenAIEmbeddingAdapter
from app.providers.llm.base import LLMProvider
from app.providers.llm.claude_adapter import ClaudeAdapter
from app.providers.llm.gemini_adapter import GeminiAdapter
from app.providers.llm.openai_adapter import OpenAIAdapter

_llm_provider: LLMProvider | None = None
_llm_registry: dict[str, LLMProvider] | None = None
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


def get_llm_registry(config: ProviderConfig | None = None) -> dict[str, LLMProvider]:
    """Get or create the LLM provider registry.

    REQ-028 §3.1: Creates adapters for all providers with valid API keys.
    Used by MeteredLLMProvider for cross-provider dispatch.

    Args:
        config: Optional provider configuration. If None and no registry
            exists, loads from environment.

    Returns:
        Dict mapping provider name to LLMProvider instance.
        Only providers with non-None API keys are included.
    """
    global _llm_registry

    if _llm_registry is None:
        if config is None:
            config = ProviderConfig.from_env()

        _llm_registry = {}
        if config.anthropic_api_key:
            _llm_registry["claude"] = ClaudeAdapter(config)
        if config.openai_api_key:
            _llm_registry["openai"] = OpenAIAdapter(config)
        if config.google_api_key:
            _llm_registry["gemini"] = GeminiAdapter(config)

    return dict(_llm_registry)


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
        elif config.embedding_provider == "gemini":
            _embedding_provider = GeminiEmbeddingAdapter(config)
        else:
            raise ValueError(f"Unknown embedding provider: {config.embedding_provider}")

    return _embedding_provider


def reset_providers() -> None:
    """Reset provider singletons.

    Used in tests to ensure isolation between test cases.
    """
    global _llm_provider, _llm_registry, _embedding_provider
    _llm_provider = None
    _llm_registry = None
    _embedding_provider = None
