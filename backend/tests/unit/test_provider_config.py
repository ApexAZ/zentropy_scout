"""Tests for ProviderConfig class.

REQ-009 §6.1: ProviderConfig is a dataclass for centralized provider configuration.
"""

import os
from unittest.mock import patch

from app.providers.config import ProviderConfig


class TestProviderConfigDefaults:
    """Test default values for ProviderConfig."""

    def test_default_embedding_dimensions(self):
        """Default embedding dimensions should be 768 to match pgvector columns."""
        config = ProviderConfig()
        assert config.embedding_dimensions == 768

    def test_default_max_tokens(self):
        """Default max tokens should be 4096."""
        config = ProviderConfig()
        assert config.default_max_tokens == 4096


class TestProviderConfigFromEnv:
    """Test ProviderConfig.from_env() loads from environment variables."""

    def test_from_env_loads_llm_provider(self):
        """from_env should load LLM_PROVIDER from environment."""
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=False):
            config = ProviderConfig.from_env()
            assert config.llm_provider == "openai"

    def test_from_env_loads_embedding_provider(self):
        """from_env should load EMBEDDING_PROVIDER from environment."""
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "cohere"}, clear=False):
            config = ProviderConfig.from_env()
            assert config.embedding_provider == "cohere"

    def test_from_env_loads_api_keys(self):
        """from_env should load API keys from environment."""
        env_vars = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "OPENAI_API_KEY": "sk-test",
            "GOOGLE_API_KEY": "google-test",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = ProviderConfig.from_env()
            assert config.anthropic_api_key == "sk-ant-test"
            assert config.openai_api_key == "sk-test"
            assert config.google_api_key == "google-test"

    def test_from_env_loads_embedding_config(self):
        """from_env should load embedding model and dimensions."""
        env_vars = {
            "EMBEDDING_MODEL": "text-embedding-ada-002",
            "EMBEDDING_DIMENSIONS": "1024",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = ProviderConfig.from_env()
            assert config.embedding_model == "text-embedding-ada-002"
            assert config.embedding_dimensions == 1024

    def test_from_env_loads_llm_defaults(self):
        """from_env should load max tokens and temperature."""
        env_vars = {
            "DEFAULT_MAX_TOKENS": "8192",
            "DEFAULT_TEMPERATURE": "0.3",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = ProviderConfig.from_env()
            assert config.default_max_tokens == 8192
            assert config.default_temperature == 0.3

    def test_from_env_loads_retry_config(self):
        """from_env should load retry configuration."""
        with patch.dict(os.environ, {"LLM_MAX_RETRIES": "5"}, clear=False):
            config = ProviderConfig.from_env()
            assert config.max_retries == 5

    def test_from_env_uses_defaults_when_not_set(self):
        """from_env should use defaults when env vars not set."""
        # Clear relevant env vars
        env_clear = {
            "LLM_PROVIDER": None,
            "EMBEDDING_PROVIDER": None,
            "EMBEDDING_MODEL": None,
        }
        # Patch to remove these vars
        original_get = os.environ.get

        def mock_get(key, default=None):
            if key in env_clear:
                return default
            return original_get(key, default)

        with (
            patch.object(os.environ, "get", mock_get),
            patch.dict(os.environ, {}, clear=False),
        ):
            config = ProviderConfig.from_env()
            assert config.llm_provider == "claude"
            assert config.embedding_provider == "gemini"
            assert config.embedding_model == "text-embedding-004"


class TestProviderConfigValidation:
    """Test ProviderConfig input validation."""

    def test_explicit_values_override_defaults(self):
        """Explicit constructor values should override defaults."""
        config = ProviderConfig(
            llm_provider="gemini",
            embedding_provider="cohere",
            default_max_tokens=2048,
        )
        assert config.llm_provider == "gemini"
        assert config.embedding_provider == "cohere"
        assert config.default_max_tokens == 2048

    def test_config_stores_model_routing_dict(self):
        """ProviderConfig should accept model routing dictionaries."""
        routing = {"extraction": "claude-3-haiku", "generation": "claude-3-sonnet"}
        config = ProviderConfig(claude_model_routing=routing)
        assert config.claude_model_routing == routing
