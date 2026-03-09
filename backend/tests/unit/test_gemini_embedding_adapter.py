"""Tests for Gemini embedding adapter (REQ-028 §7).

Tests behavior of Gemini embedding adapter:
- Embedding generation for single and batch inputs
- Batching logic for large input lists
- Token usage tracking (character-based estimation)
- Provider name identification
- Error handling via shared Gemini error classifier
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.config import ProviderConfig
from app.providers.embedding.gemini_adapter import GeminiEmbeddingAdapter
from app.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    ContextLengthError,
    ProviderError,
    RateLimitError,
    TransientError,
)


@pytest.fixture
def config():
    """Provider config with test Google API key."""
    return ProviderConfig(
        google_api_key="test-google-key",
        embedding_model="text-embedding-004",
        embedding_dimensions=768,
    )


@pytest.fixture
def mock_genai_client():
    """Mock google.genai Client for embedding tests."""
    with patch(
        "app.providers.embedding.gemini_adapter.genai.Client"
    ) as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        yield mock_client


def _make_embed_response(
    vectors: list[list[float]],
    billable_chars: int | None = None,
) -> MagicMock:
    """Create a mock Gemini embed_content response.

    Args:
        vectors: List of embedding vectors.
        billable_chars: Billable character count (None = no metadata).
    """
    embeddings = [MagicMock(values=v) for v in vectors]
    response = MagicMock()
    response.embeddings = embeddings
    if billable_chars is not None:
        response.metadata = MagicMock(billable_character_count=billable_chars)
    else:
        response.metadata = None
    return response


class TestGeminiEmbeddingAdapterEmbed:
    """Test embed() method behavior."""

    @pytest.mark.asyncio
    async def test_embed_single_text_returns_correct_result(
        self, config, mock_genai_client
    ):
        """embed() should return result with correct vectors, model, and dimensions."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response([[0.1] * 768], billable_chars=13)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(["Hello, world!"])

        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 768
        assert result.model == "text-embedding-004"
        assert result.dimensions == 768

    @pytest.mark.asyncio
    async def test_embed_batch_returns_vectors_in_order(
        self, config, mock_genai_client
    ):
        """embed() should return vectors in same order as input texts."""
        vectors = [[float(i)] * 768 for i in range(3)]
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response(vectors, billable_chars=30)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(["First", "Second", "Third"])

        assert len(result.vectors) == 3
        assert result.vectors[0][0] == 0.0
        assert result.vectors[1][0] == 1.0
        assert result.vectors[2][0] == 2.0

    @pytest.mark.asyncio
    async def test_embed_calls_api_with_correct_parameters(
        self, config, mock_genai_client
    ):
        """embed() should call Gemini API with correct model and contents."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response([[0.0] * 768], billable_chars=9)
        )

        adapter = GeminiEmbeddingAdapter(config)
        await adapter.embed(["Test text"])

        mock_genai_client.aio.models.embed_content.assert_called_once()
        call_kwargs = mock_genai_client.aio.models.embed_content.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-004"
        assert call_kwargs["contents"] == ["Test text"]

    @pytest.mark.asyncio
    async def test_embed_estimates_tokens_from_characters(
        self, config, mock_genai_client
    ):
        """embed() should estimate total_tokens from billable character count."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response([[0.0] * 768], billable_chars=100)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(["Some text to embed"])

        # Gemini reports characters, not tokens. Estimate: chars // 4
        assert result.total_tokens == 25

    @pytest.mark.asyncio
    async def test_embed_handles_missing_metadata(self, config, mock_genai_client):
        """embed() should fall back to text-length estimation when metadata is missing."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response([[0.0] * 768], billable_chars=None)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(["Text"])

        # Fallback: len("Text") // 4 = 1
        assert result.total_tokens == 1

    @pytest.mark.asyncio
    async def test_embed_handles_zero_billable_characters(
        self, config, mock_genai_client
    ):
        """embed() should fall back to text-length estimation when billable chars is 0."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response([[0.0] * 768], billable_chars=0)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(["Text"])

        # billable_character_count=0 is falsy, so fallback kicks in
        assert result.total_tokens == 1

    @pytest.mark.asyncio
    async def test_embed_empty_list_returns_empty_result(
        self, config, mock_genai_client
    ):
        """embed() with empty list should return empty result without API call."""
        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed([])

        assert result.vectors == []
        assert result.total_tokens == 0
        assert result.model == "text-embedding-004"
        assert result.dimensions == 768
        # Should not have called the API
        mock_genai_client.aio.models.embed_content.assert_not_called()


class TestGeminiEmbeddingAdapterBatching:
    """Test batching behavior for large input lists."""

    @pytest.mark.asyncio
    async def test_small_batch_uses_single_api_call(self, config, mock_genai_client):
        """Batches <= 100 should use single API call."""
        texts = ["text"] * 50
        vectors = [[0.0] * 768 for _ in texts]
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response(vectors, billable_chars=250)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        assert mock_genai_client.aio.models.embed_content.call_count == 1
        assert len(result.vectors) == 50
        assert result.total_tokens == 62  # 250 // 4

    @pytest.mark.asyncio
    async def test_large_batch_chunks_into_multiple_calls(
        self, config, mock_genai_client
    ):
        """Batches > 100 should be chunked into multiple API calls."""
        texts = ["text"] * 250

        async def mock_embed(*, model, contents):  # noqa: ARG001
            vectors = [[0.0] * 768 for _ in contents]
            return _make_embed_response(vectors, billable_chars=len(contents) * 5)

        mock_genai_client.aio.models.embed_content = AsyncMock(side_effect=mock_embed)

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        # 250 texts / 100 per batch = 3 calls (100 + 100 + 50)
        assert mock_genai_client.aio.models.embed_content.call_count == 3
        assert len(result.vectors) == 250

    @pytest.mark.asyncio
    async def test_large_batch_returns_unknown_token_count(
        self, config, mock_genai_client
    ):
        """Chunked batches should return -1 for total_tokens."""
        texts = ["text"] * 150

        async def mock_embed(*, model, contents):  # noqa: ARG001
            vectors = [[0.0] * 768 for _ in contents]
            return _make_embed_response(vectors, billable_chars=len(contents) * 5)

        mock_genai_client.aio.models.embed_content = AsyncMock(side_effect=mock_embed)

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        assert result.total_tokens == -1

    @pytest.mark.asyncio
    async def test_exactly_100_uses_single_call(self, config, mock_genai_client):
        """Exactly 100 texts should use single API call (boundary check)."""
        texts = ["text"] * 100
        vectors = [[0.0] * 768 for _ in texts]
        mock_genai_client.aio.models.embed_content = AsyncMock(
            return_value=_make_embed_response(vectors, billable_chars=500)
        )

        adapter = GeminiEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        assert mock_genai_client.aio.models.embed_content.call_count == 1
        assert len(result.vectors) == 100
        assert result.total_tokens == 125  # 500 // 4


class TestGeminiEmbeddingAdapterErrors:
    """Test error handling via shared Gemini error classifier."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_is_classified(self, config, mock_genai_client):
        """Rate limit errors should be classified as RateLimitError."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("Resource exhausted: quota exceeded")
        )

        adapter = GeminiEmbeddingAdapter(config)
        with pytest.raises(RateLimitError):
            await adapter.embed(["Test"])

    @pytest.mark.asyncio
    async def test_auth_error_is_classified(self, config, mock_genai_client):
        """Auth errors should be classified as AuthenticationError."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("Permission denied: invalid API key")
        )

        adapter = GeminiEmbeddingAdapter(config)
        with pytest.raises(AuthenticationError):
            await adapter.embed(["Test"])

    @pytest.mark.asyncio
    async def test_context_length_error_is_classified(self, config, mock_genai_client):
        """Context length errors should be classified as ContextLengthError."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("context window exceeded: token limit reached")
        )

        adapter = GeminiEmbeddingAdapter(config)
        with pytest.raises(ContextLengthError):
            await adapter.embed(["Test"])

    @pytest.mark.asyncio
    async def test_content_filter_error_is_classified(self, config, mock_genai_client):
        """Content filter errors should be classified as ContentFilterError."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("safety filter: content blocked by policy")
        )

        adapter = GeminiEmbeddingAdapter(config)
        with pytest.raises(ContentFilterError):
            await adapter.embed(["Test"])

    @pytest.mark.asyncio
    async def test_transient_error_is_classified(self, config, mock_genai_client):
        """Transient errors should be classified as TransientError."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("service unavailable: 503 error")
        )

        adapter = GeminiEmbeddingAdapter(config)
        with pytest.raises(TransientError):
            await adapter.embed(["Test"])

    @pytest.mark.asyncio
    async def test_unknown_error_is_classified_as_provider_error(
        self, config, mock_genai_client
    ):
        """Unknown errors should be classified as ProviderError."""
        mock_genai_client.aio.models.embed_content = AsyncMock(
            side_effect=Exception("Something unexpected happened")
        )

        adapter = GeminiEmbeddingAdapter(config)
        with pytest.raises(ProviderError):
            await adapter.embed(["Test"])
