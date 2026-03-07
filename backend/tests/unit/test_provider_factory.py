"""Tests for provider factory functions.

REQ-009 §6.3: Singleton pattern for provider instances.
REQ-028 §3: Provider registry factory for cross-provider dispatch.
"""

from unittest.mock import patch

import pytest

from app.providers.config import ProviderConfig
from app.providers.factory import (
    get_embedding_provider,
    get_llm_provider,
    get_llm_registry,
    reset_providers,
)

_PROVIDER_CLAUDE = "claude"
_PROVIDER_OPENAI = "openai"
_PROVIDER_GEMINI = "gemini"
_TEST_API_KEY = "test-key"


class TestGetLLMProvider:
    """Test get_llm_provider() factory function."""

    def setup_method(self) -> None:
        """Reset singletons before each test."""
        reset_providers()

    def test_returns_llm_provider_instance(self) -> None:
        """Factory should return an LLMProvider instance."""
        config = ProviderConfig(llm_provider=_PROVIDER_CLAUDE)
        provider = get_llm_provider(config)
        assert provider is not None

    def test_singleton_returns_same_instance(self) -> None:
        """Subsequent calls should return the same instance."""
        config = ProviderConfig(llm_provider=_PROVIDER_CLAUDE)
        provider1 = get_llm_provider(config)
        provider2 = get_llm_provider()  # No config, uses cached
        assert provider1 is provider2

    def test_uses_config_from_env_when_none_provided(self) -> None:
        """When no config provided, should load from environment."""
        with patch("app.providers.factory.ProviderConfig.from_env") as mock_from_env:
            mock_config = ProviderConfig(llm_provider=_PROVIDER_CLAUDE)
            mock_from_env.return_value = mock_config
            get_llm_provider()
            mock_from_env.assert_called_once()

    def test_raises_for_unknown_provider(self) -> None:
        """Should raise ValueError for unknown provider."""
        config = ProviderConfig(llm_provider="unknown_provider")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider(config)


class TestGetEmbeddingProvider:
    """Test get_embedding_provider() factory function."""

    def setup_method(self) -> None:
        """Reset singletons before each test."""
        reset_providers()

    def test_returns_embedding_provider_instance(self) -> None:
        """Factory should return an EmbeddingProvider instance."""
        config = ProviderConfig(
            embedding_provider=_PROVIDER_OPENAI,
            openai_api_key=_TEST_API_KEY,
        )
        with patch("app.providers.embedding.openai_adapter.AsyncOpenAI"):
            provider = get_embedding_provider(config)
            assert provider is not None

    def test_singleton_returns_same_instance(self) -> None:
        """Subsequent calls should return the same instance."""
        config = ProviderConfig(
            embedding_provider=_PROVIDER_OPENAI,
            openai_api_key=_TEST_API_KEY,
        )
        with patch("app.providers.embedding.openai_adapter.AsyncOpenAI"):
            provider1 = get_embedding_provider(config)
            provider2 = get_embedding_provider()  # No config, uses cached
            assert provider1 is provider2

    def test_raises_for_unknown_provider(self) -> None:
        """Should raise ValueError for unknown provider."""
        config = ProviderConfig(embedding_provider="unknown_provider")
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider(config)


class TestGetLLMRegistry:
    """Test get_llm_registry() factory function.

    REQ-028 §3: Creates adapters for all providers with valid API keys.
    """

    def setup_method(self) -> None:
        """Reset singletons before each test."""
        reset_providers()

    def test_creates_adapter_for_claude_when_key_present(self) -> None:
        """Registry should include Claude adapter when ANTHROPIC_API_KEY is set."""
        config = ProviderConfig(anthropic_api_key=_TEST_API_KEY)
        registry = get_llm_registry(config)
        assert _PROVIDER_CLAUDE in registry
        assert registry[_PROVIDER_CLAUDE].provider_name == _PROVIDER_CLAUDE

    def test_creates_adapter_for_gemini_when_key_present(self) -> None:
        """Registry should include Gemini adapter when GOOGLE_API_KEY is set."""
        config = ProviderConfig(google_api_key=_TEST_API_KEY)
        registry = get_llm_registry(config)
        assert _PROVIDER_GEMINI in registry
        assert registry[_PROVIDER_GEMINI].provider_name == _PROVIDER_GEMINI

    def test_creates_adapter_for_openai_when_key_present(self) -> None:
        """Registry should include OpenAI adapter when OPENAI_API_KEY is set."""
        config = ProviderConfig(openai_api_key=_TEST_API_KEY)
        registry = get_llm_registry(config)
        assert _PROVIDER_OPENAI in registry
        assert registry[_PROVIDER_OPENAI].provider_name == _PROVIDER_OPENAI

    def test_creates_all_adapters_when_all_keys_present(self) -> None:
        """Registry should include all providers when all API keys are set."""
        config = ProviderConfig(
            anthropic_api_key=_TEST_API_KEY,
            openai_api_key=_TEST_API_KEY,
            google_api_key=_TEST_API_KEY,
        )
        registry = get_llm_registry(config)
        assert len(registry) == 3
        assert set(registry.keys()) == {
            _PROVIDER_CLAUDE,
            _PROVIDER_OPENAI,
            _PROVIDER_GEMINI,
        }

    def test_skips_providers_without_keys(self) -> None:
        """Registry should not include providers without API keys."""
        config = ProviderConfig(
            anthropic_api_key=_TEST_API_KEY,
            openai_api_key=None,
            google_api_key=None,
        )
        registry = get_llm_registry(config)
        assert _PROVIDER_CLAUDE in registry
        assert _PROVIDER_OPENAI not in registry
        assert _PROVIDER_GEMINI not in registry

    def test_empty_registry_when_no_keys(self) -> None:
        """Registry should be empty when no API keys are configured."""
        config = ProviderConfig(
            anthropic_api_key=None,
            openai_api_key=None,
            google_api_key=None,
        )
        registry = get_llm_registry(config)
        assert len(registry) == 0

    def test_subsequent_calls_return_equal_registries(self) -> None:
        """Subsequent calls should return registries with the same adapters."""
        config = ProviderConfig(anthropic_api_key=_TEST_API_KEY)
        registry1 = get_llm_registry(config)
        registry2 = get_llm_registry()
        assert registry1.keys() == registry2.keys()
        assert registry1[_PROVIDER_CLAUDE] is registry2[_PROVIDER_CLAUDE]

    def test_uses_config_from_env_when_none_provided(self) -> None:
        """When no config provided, should load from environment."""
        with patch("app.providers.factory.ProviderConfig.from_env") as mock_from_env:
            mock_config = ProviderConfig(anthropic_api_key=_TEST_API_KEY)
            mock_from_env.return_value = mock_config
            get_llm_registry()
            mock_from_env.assert_called_once()

    def test_reset_clears_registry(self) -> None:
        """reset_providers should clear the registry singleton."""
        config = ProviderConfig(anthropic_api_key=_TEST_API_KEY)
        registry1 = get_llm_registry(config)
        reset_providers()
        registry2 = get_llm_registry(config)
        assert registry1 is not registry2


class TestResetProviders:
    """Test reset_providers() for test isolation."""

    def test_reset_clears_llm_singleton(self) -> None:
        """reset_providers should clear the LLM singleton."""
        config = ProviderConfig(llm_provider=_PROVIDER_CLAUDE)
        provider1 = get_llm_provider(config)
        reset_providers()
        provider2 = get_llm_provider(config)
        # After reset, should be a new instance
        assert provider1 is not provider2

    def test_reset_clears_embedding_singleton(self) -> None:
        """reset_providers should clear the embedding singleton."""
        config = ProviderConfig(
            embedding_provider=_PROVIDER_OPENAI,
            openai_api_key=_TEST_API_KEY,
        )
        with patch("app.providers.embedding.openai_adapter.AsyncOpenAI"):
            provider1 = get_embedding_provider(config)
            reset_providers()
            provider2 = get_embedding_provider(config)
            # After reset, should be a new instance
            assert provider1 is not provider2
