"""Tests for provider factory functions.

REQ-009 §6.3: Singleton pattern for provider instances.
"""

from unittest.mock import patch

from app.providers.config import ProviderConfig
from app.providers.factory import (
    get_embedding_provider,
    get_llm_provider,
    reset_providers,
)


class TestGetLLMProvider:
    """Test get_llm_provider() factory function."""

    def setup_method(self):
        """Reset singletons before each test."""
        reset_providers()

    def test_returns_llm_provider_instance(self):
        """Factory should return an LLMProvider instance."""
        config = ProviderConfig(llm_provider="claude")
        provider = get_llm_provider(config)
        assert provider is not None

    def test_singleton_returns_same_instance(self):
        """Subsequent calls should return the same instance."""
        config = ProviderConfig(llm_provider="claude")
        provider1 = get_llm_provider(config)
        provider2 = get_llm_provider()  # No config, uses cached
        assert provider1 is provider2

    def test_uses_config_from_env_when_none_provided(self):
        """When no config provided, should load from environment."""
        with patch("app.providers.factory.ProviderConfig.from_env") as mock_from_env:
            mock_config = ProviderConfig(llm_provider="claude")
            mock_from_env.return_value = mock_config
            get_llm_provider()
            mock_from_env.assert_called_once()

    def test_raises_for_unknown_provider(self):
        """Should raise ValueError for unknown provider."""
        import pytest

        config = ProviderConfig(llm_provider="unknown_provider")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_llm_provider(config)


class TestGetEmbeddingProvider:
    """Test get_embedding_provider() factory function."""

    def setup_method(self):
        """Reset singletons before each test."""
        reset_providers()

    def test_returns_embedding_provider_instance(self):
        """Factory should return an EmbeddingProvider instance."""
        config = ProviderConfig(embedding_provider="openai")
        provider = get_embedding_provider(config)
        assert provider is not None

    def test_singleton_returns_same_instance(self):
        """Subsequent calls should return the same instance."""
        config = ProviderConfig(embedding_provider="openai")
        provider1 = get_embedding_provider(config)
        provider2 = get_embedding_provider()  # No config, uses cached
        assert provider1 is provider2

    def test_raises_for_unknown_provider(self):
        """Should raise ValueError for unknown provider."""
        import pytest

        config = ProviderConfig(embedding_provider="unknown_provider")
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            get_embedding_provider(config)


class TestResetProviders:
    """Test reset_providers() for test isolation."""

    def test_reset_clears_llm_singleton(self):
        """reset_providers should clear the LLM singleton."""
        config = ProviderConfig(llm_provider="claude")
        provider1 = get_llm_provider(config)
        reset_providers()
        provider2 = get_llm_provider(config)
        # After reset, should be a new instance
        assert provider1 is not provider2

    def test_reset_clears_embedding_singleton(self):
        """reset_providers should clear the embedding singleton."""
        config = ProviderConfig(embedding_provider="openai")
        provider1 = get_embedding_provider(config)
        reset_providers()
        provider2 = get_embedding_provider(config)
        # After reset, should be a new instance
        assert provider1 is not provider2
