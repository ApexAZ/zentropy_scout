"""Tests for provider_name property on all LLM and embedding adapters.

REQ-020 §6.2: Every adapter must expose provider_name so the metering
wrapper can identify which provider handled a call.
"""

from typing import Any

import pytest

from app.providers.config import ProviderConfig
from app.providers.embedding.base import EmbeddingResult
from app.providers.embedding.mock_adapter import MockEmbeddingProvider
from app.providers.llm.base import LLMProvider, TaskType
from app.providers.llm.claude_adapter import ClaudeAdapter
from app.providers.llm.gemini_adapter import GeminiAdapter
from app.providers.llm.mock_adapter import MockLLMProvider
from app.providers.llm.openai_adapter import OpenAIAdapter


def _make_config(**overrides: Any) -> ProviderConfig:
    """Create a ProviderConfig with dummy keys for adapter construction."""
    defaults: dict[str, Any] = {
        "anthropic_api_key": "sk-ant-test",
        "openai_api_key": "sk-test",
        "google_api_key": "google-test",
    }
    defaults.update(overrides)
    return ProviderConfig(**defaults)


# =============================================================================
# LLM Adapters
# =============================================================================


class TestClaudeAdapterProviderName:
    """ClaudeAdapter.provider_name returns 'claude'."""

    def test_returns_claude(self) -> None:
        adapter = ClaudeAdapter(_make_config())
        assert adapter.provider_name == "claude"


class TestOpenAIAdapterProviderName:
    """OpenAIAdapter.provider_name returns 'openai'."""

    def test_returns_openai(self) -> None:
        adapter = OpenAIAdapter(_make_config())
        assert adapter.provider_name == "openai"


class TestGeminiAdapterProviderName:
    """GeminiAdapter.provider_name returns 'gemini'."""

    def test_returns_gemini(self) -> None:
        adapter = GeminiAdapter(_make_config())
        assert adapter.provider_name == "gemini"


class TestMockLLMProviderName:
    """MockLLMProvider.provider_name returns 'mock'."""

    def test_returns_mock(self) -> None:
        adapter = MockLLMProvider()
        assert adapter.provider_name == "mock"


# =============================================================================
# Embedding Adapters
# =============================================================================


class TestOpenAIEmbeddingProviderName:
    """OpenAIEmbeddingAdapter.provider_name returns 'openai'."""

    def test_returns_openai(self) -> None:
        from app.providers.embedding.openai_adapter import OpenAIEmbeddingAdapter

        adapter = OpenAIEmbeddingAdapter(_make_config())
        assert adapter.provider_name == "openai"


class TestMockEmbeddingProviderName:
    """MockEmbeddingProvider.provider_name returns 'mock'."""

    def test_returns_mock(self) -> None:
        adapter = MockEmbeddingProvider()
        assert adapter.provider_name == "mock"


# =============================================================================
# Abstract enforcement
# =============================================================================


class TestAbstractEnforcement:
    """Base classes enforce provider_name as abstract."""

    def test_llm_provider_requires_provider_name(self) -> None:
        """Cannot instantiate LLMProvider subclass without provider_name."""

        class IncompleteLLM(LLMProvider):
            async def complete(self, _messages, _task, **_kwargs):  # type: ignore[override]
                ...

            async def stream(self, _messages, _task, **_kwargs):  # type: ignore[override]
                yield ""

            def get_model_for_task(self, _task: TaskType) -> str:
                return "test"

        with pytest.raises(TypeError, match="provider_name"):
            IncompleteLLM(_make_config())  # type: ignore[abstract]

    def test_embedding_provider_requires_provider_name(self) -> None:
        """Cannot instantiate EmbeddingProvider subclass without provider_name."""
        from app.providers.embedding.base import EmbeddingProvider

        class IncompleteEmbedding(EmbeddingProvider):
            async def embed(self, _texts: list[str]) -> EmbeddingResult: ...

            @property
            def dimensions(self) -> int:
                return 1536

        with pytest.raises(TypeError, match="provider_name"):
            IncompleteEmbedding(_make_config())  # type: ignore[abstract]
