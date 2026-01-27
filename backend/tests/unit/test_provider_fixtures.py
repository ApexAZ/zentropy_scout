"""Tests for provider test fixtures (REQ-009 §9.2).

Tests the pytest fixtures for MockLLMProvider injection:
- mock_llm fixture creation and cleanup
- Provider singleton injection
- Test isolation between tests
"""

import pytest

from app.providers import factory
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType
from app.providers.llm.mock_adapter import MockLLMProvider


class TestMockLLMFixture:
    """Test the mock_llm pytest fixture."""

    def test_mock_llm_fixture_exists(self, mock_llm):
        """mock_llm fixture should be available."""
        assert mock_llm is not None

    def test_mock_llm_fixture_returns_mock_provider(self, mock_llm):
        """mock_llm fixture should return a MockLLMProvider instance."""
        assert isinstance(mock_llm, MockLLMProvider)

    def test_mock_llm_fixture_is_llm_provider(self, mock_llm):
        """mock_llm fixture should return an LLMProvider instance."""
        assert isinstance(mock_llm, LLMProvider)

    def test_mock_llm_fixture_has_empty_calls(self, mock_llm):
        """mock_llm fixture should start with no recorded calls."""
        assert mock_llm.calls == []


class TestMockLLMFixtureInjection:
    """Test that mock_llm fixture is properly injected into the factory."""

    def test_get_llm_provider_returns_mock(self, mock_llm):
        """get_llm_provider() should return the injected mock."""
        provider = factory.get_llm_provider()
        assert provider is mock_llm

    def test_mock_is_singleton(self, mock_llm):
        """Multiple calls to get_llm_provider() should return same mock."""
        provider1 = factory.get_llm_provider()
        provider2 = factory.get_llm_provider()
        assert provider1 is provider2
        assert provider1 is mock_llm


class TestMockLLMFixtureResponses:
    """Test pre-configured responses in mock_llm fixture."""

    @pytest.mark.anyio
    async def test_skill_extraction_response(self, mock_llm):
        """mock_llm should have pre-configured SKILL_EXTRACTION response."""
        messages = [LLMMessage(role="user", content="Extract skills")]
        response = await mock_llm.complete(messages, TaskType.SKILL_EXTRACTION)

        # Should return JSON with skills
        assert "skills" in response.content
        assert "Python" in response.content

    @pytest.mark.anyio
    async def test_cover_letter_response(self, mock_llm):
        """mock_llm should have pre-configured COVER_LETTER response."""
        messages = [LLMMessage(role="user", content="Write cover letter")]
        response = await mock_llm.complete(messages, TaskType.COVER_LETTER)

        # Should return cover letter text
        assert "Dear" in response.content or "Hiring" in response.content


class TestMockLLMFixtureCleanup:
    """Test that mock_llm fixture properly cleans up after tests."""

    def test_first_test_uses_mock(self, mock_llm):  # noqa: ARG002
        """First test should have mock injected."""
        provider = factory.get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

    def test_second_test_has_fresh_mock(self, mock_llm):
        """Second test should have a fresh mock (isolation)."""
        # This test verifies isolation - the mock should have no calls
        # even if the previous test made calls
        assert mock_llm.calls == []


class TestMockLLMFixtureCallTracking:
    """Test that mock_llm fixture tracks calls correctly."""

    @pytest.mark.anyio
    async def test_calls_are_recorded(self, mock_llm):
        """Calls through get_llm_provider() should be recorded on mock."""
        provider = factory.get_llm_provider()
        messages = [LLMMessage(role="user", content="Hello")]

        await provider.complete(messages, TaskType.CHAT_RESPONSE)

        assert len(mock_llm.calls) == 1
        assert mock_llm.calls[0]["task"] == TaskType.CHAT_RESPONSE

    @pytest.mark.anyio
    async def test_assert_called_with_task_works(self, mock_llm):
        """assert_called_with_task() should work with fixture."""
        provider = factory.get_llm_provider()
        messages = [LLMMessage(role="user", content="Extract")]

        await provider.complete(messages, TaskType.EXTRACTION)

        # Should not raise
        mock_llm.assert_called_with_task(TaskType.EXTRACTION)


class TestMockEmbeddingFixture:
    """Test the mock_embedding pytest fixture."""

    def test_mock_embedding_fixture_exists(self, mock_embedding):
        """mock_embedding fixture should be available."""
        assert mock_embedding is not None

    def test_mock_embedding_returns_mock(self, mock_embedding):
        """mock_embedding fixture should return a mock provider."""
        from app.providers.embedding.base import EmbeddingProvider

        assert isinstance(mock_embedding, EmbeddingProvider)

    def test_get_embedding_provider_returns_mock(self, mock_embedding):
        """get_embedding_provider() should return the injected mock."""
        provider = factory.get_embedding_provider()
        assert provider is mock_embedding

    @pytest.mark.anyio
    async def test_mock_embedding_returns_vectors(self, mock_embedding):
        """mock_embedding should return fixed-dimension vectors."""
        result = await mock_embedding.embed(["test text"])

        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 1536  # text-embedding-3-small dimension
