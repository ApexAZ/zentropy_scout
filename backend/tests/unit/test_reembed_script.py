"""Tests for re-embedding script (REQ-028 §8.1).

Tests behavior of the re-embedding helper functions:
- embed_fn wrapper creates correct callable
- Script entry point logs provider info
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.embedding.base import EmbeddingResult

_TEST_MODEL = "text-embedding-004"
_TEST_DIMENSIONS = 768


@pytest.fixture()
def mock_provider() -> MagicMock:
    """Create a mock embedding provider returning a known vector."""
    provider = MagicMock()
    provider.embed = AsyncMock(
        return_value=EmbeddingResult(
            vectors=[[0.1] * _TEST_DIMENSIONS],
            model=_TEST_MODEL,
            dimensions=_TEST_DIMENSIONS,
            total_tokens=10,
        )
    )
    return provider


class TestEmbedFnWrapper:
    """Test _embed_fn creates correct callable for generators."""

    @pytest.mark.asyncio
    async def test_embed_fn_calls_provider_and_returns_vectors(
        self, mock_provider: MagicMock
    ) -> None:
        """_embed_fn should wrap provider.embed and return vectors."""
        from scripts.reembed_all import _embed_fn

        embed = _embed_fn(mock_provider)
        result = await embed("Hello world")

        assert result == [[0.1] * _TEST_DIMENSIONS]
        mock_provider.embed.assert_called_once_with(["Hello world"])

    @pytest.mark.asyncio
    async def test_embed_fn_passes_single_text_as_list(
        self, mock_provider: MagicMock
    ) -> None:
        """_embed_fn should wrap single text input into a list for batch API."""
        from scripts.reembed_all import _embed_fn

        embed = _embed_fn(mock_provider)
        await embed("Test text")

        # Should have been called with ["Test text"], not "Test text"
        call_args = mock_provider.embed.call_args[0][0]
        assert call_args == ["Test text"]
