"""Tests for provider_name property on all LLM and embedding adapters.

REQ-020 §6.2: Every adapter must expose provider_name so the metering
wrapper can identify which provider handled a call.
"""

from typing import Any

import pytest

from app.providers.config import ProviderConfig
from app.providers.embedding.base import EmbeddingResult
from app.providers.embedding.mock_adapter import MockEmbeddingProvider
from app.providers.embedding.openai_adapter import OpenAIEmbeddingAdapter
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
# Provider Name — Parametrized
# =============================================================================


@pytest.mark.parametrize(
    ("adapter_factory", "expected_name"),
    [
        (lambda cfg: ClaudeAdapter(cfg), "claude"),
        (lambda cfg: OpenAIAdapter(cfg), "openai"),
        (lambda cfg: GeminiAdapter(cfg), "gemini"),
        (lambda _cfg: MockLLMProvider(), "mock"),
        (lambda cfg: OpenAIEmbeddingAdapter(cfg), "openai"),
        (lambda _cfg: MockEmbeddingProvider(), "mock"),
    ],
    ids=[
        "claude-llm",
        "openai-llm",
        "gemini-llm",
        "mock-llm",
        "openai-embedding",
        "mock-embedding",
    ],
)
def test_adapter_exposes_correct_provider_name(adapter_factory, expected_name) -> None:
    """Each adapter's provider_name matches its provider for metering lookup."""
    adapter = adapter_factory(_make_config())
    assert adapter.provider_name == expected_name


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

            def get_model_for_task(self, _task: TaskType) -> str:  # pyright: ignore[reportIncompatibleMethodOverride]
                return "test"

        with pytest.raises(TypeError, match="provider_name"):
            IncompleteLLM(_make_config())  # type: ignore[abstract]

    def test_embedding_provider_requires_provider_name(self) -> None:
        """Cannot instantiate EmbeddingProvider subclass without provider_name."""
        from app.providers.embedding.base import EmbeddingProvider

        class IncompleteEmbedding(EmbeddingProvider):
            async def embed(self, _texts: list[str]) -> EmbeddingResult: ...  # pyright: ignore[reportIncompatibleMethodOverride]

            @property
            def dimensions(self) -> int:
                return 768

        with pytest.raises(TypeError, match="provider_name"):
            IncompleteEmbedding(_make_config())  # type: ignore[abstract]
