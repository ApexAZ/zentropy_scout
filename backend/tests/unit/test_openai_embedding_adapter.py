"""Tests for OpenAI embedding adapter (REQ-009 §5.2).

Tests behavior of OpenAI embedding adapter:
- Embedding generation for single and batch inputs
- Batching logic for large input lists
- Token usage tracking
- Error handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.config import ProviderConfig
from app.providers.embedding.base import EmbeddingResult
from app.providers.embedding.openai_adapter import OpenAIEmbeddingAdapter


@pytest.fixture
def config():
    """Provider config with test API key."""
    return ProviderConfig(
        openai_api_key="test-api-key",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1536,
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding tests."""
    with patch(
        "app.providers.embedding.openai_adapter.AsyncOpenAI"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.mark.usefixtures("mock_openai_client")
class TestOpenAIEmbeddingAdapterInitialization:
    """Test adapter initialization."""

    def test_initializes_with_config(self, config):
        """Adapter should initialize with config and create client."""
        adapter = OpenAIEmbeddingAdapter(config)
        assert adapter.config == config
        assert adapter._model == "text-embedding-3-small"
        assert adapter._dimensions == 1536

    def test_dimensions_property_returns_configured_value(self, config):
        """dimensions property should return the configured embedding dimensions."""
        adapter = OpenAIEmbeddingAdapter(config)
        assert adapter.dimensions == 1536

    def test_dimensions_respects_config(self):
        """dimensions should match config value (behavior, not hardcoded)."""
        config_3072 = ProviderConfig(
            openai_api_key="test",
            embedding_model="text-embedding-3-large",
            embedding_dimensions=3072,
        )
        adapter = OpenAIEmbeddingAdapter(config_3072)
        assert adapter.dimensions == 3072


class TestOpenAIEmbeddingAdapterEmbed:
    """Test embed() method behavior."""

    @pytest.mark.asyncio
    async def test_embed_single_text_returns_embedding_result(
        self, config, mock_openai_client
    ):
        """embed() should return EmbeddingResult with correct structure."""
        # Setup mock response
        mock_embedding_data = MagicMock()
        mock_embedding_data.embedding = [0.1] * 1536
        mock_embedding_data.index = 0

        mock_response = MagicMock()
        mock_response.data = [mock_embedding_data]
        mock_response.usage.total_tokens = 5

        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(["Hello, world!"])

        assert isinstance(result, EmbeddingResult)
        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 1536
        assert result.model == "text-embedding-3-small"
        assert result.dimensions == 1536
        assert result.total_tokens == 5

    @pytest.mark.asyncio
    async def test_embed_batch_returns_vectors_in_order(
        self, config, mock_openai_client
    ):
        """embed() should return vectors in same order as input texts."""
        texts = ["First text", "Second text", "Third text"]

        # Create distinct embeddings for verification
        mock_embeddings = []
        for i, _ in enumerate(texts):
            mock_data = MagicMock()
            mock_data.embedding = [float(i)] * 1536  # Distinct vector
            mock_data.index = i
            mock_embeddings.append(mock_data)

        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        mock_response.usage.total_tokens = 15

        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        assert len(result.vectors) == 3
        # Verify order is preserved
        assert result.vectors[0][0] == 0.0
        assert result.vectors[1][0] == 1.0
        assert result.vectors[2][0] == 2.0

    @pytest.mark.asyncio
    async def test_embed_calls_api_with_correct_parameters(
        self, config, mock_openai_client
    ):
        """embed() should call OpenAI API with correct model and inputs."""
        mock_embedding_data = MagicMock()
        mock_embedding_data.embedding = [0.0] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding_data]
        mock_response.usage.total_tokens = 5

        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIEmbeddingAdapter(config)
        await adapter.embed(["Test text"])

        mock_openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["Test text"],
        )

    @pytest.mark.asyncio
    async def test_embed_tracks_token_usage(self, config, mock_openai_client):
        """embed() should include total_tokens in result."""
        mock_embedding_data = MagicMock()
        mock_embedding_data.embedding = [0.0] * 1536

        mock_response = MagicMock()
        mock_response.data = [mock_embedding_data]
        mock_response.usage.total_tokens = 42

        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(["Some text to embed"])

        assert result.total_tokens == 42


class TestOpenAIEmbeddingAdapterBatching:
    """Test batching behavior for large input lists."""

    @pytest.mark.asyncio
    async def test_small_batch_uses_single_api_call(self, config, mock_openai_client):
        """Batches <= 2048 should use single API call."""
        texts = ["text"] * 100  # Well under limit

        mock_embeddings = [MagicMock(embedding=[0.0] * 1536) for _ in texts]
        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        mock_response.usage.total_tokens = 500

        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        assert mock_openai_client.embeddings.create.call_count == 1
        assert len(result.vectors) == 100
        assert result.total_tokens == 500

    @pytest.mark.asyncio
    async def test_large_batch_chunks_into_multiple_calls(
        self, config, mock_openai_client
    ):
        """Batches > 2048 should be chunked into multiple API calls."""
        texts = ["text"] * 3000  # Over 2048 limit

        def create_mock_response(input_texts):
            mock_embeddings = [MagicMock(embedding=[0.0] * 1536) for _ in input_texts]
            mock_response = MagicMock()
            mock_response.data = mock_embeddings
            mock_response.usage.total_tokens = len(input_texts) * 5
            return mock_response

        # Side effect to return appropriate response for each chunk
        async def mock_create(*, model, input):  # noqa: ARG001
            return create_mock_response(input)

        mock_openai_client.embeddings.create = AsyncMock(side_effect=mock_create)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        # Should have made 2 calls: 2048 + 952
        assert mock_openai_client.embeddings.create.call_count == 2
        assert len(result.vectors) == 3000

    @pytest.mark.asyncio
    async def test_large_batch_returns_unknown_token_count(
        self, config, mock_openai_client
    ):
        """Chunked batches should return -1 for total_tokens."""
        texts = ["text"] * 3000

        def create_mock_response(input_texts):
            mock_embeddings = [MagicMock(embedding=[0.0] * 1536) for _ in input_texts]
            mock_response = MagicMock()
            mock_response.data = mock_embeddings
            mock_response.usage.total_tokens = len(input_texts) * 5
            return mock_response

        async def mock_create(*, model, input):  # noqa: ARG001
            return create_mock_response(input)

        mock_openai_client.embeddings.create = AsyncMock(side_effect=mock_create)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        # When chunking, total_tokens is unknown (-1)
        assert result.total_tokens == -1

    @pytest.mark.asyncio
    async def test_exactly_2048_uses_single_call(self, config, mock_openai_client):
        """Exactly 2048 texts should use single API call (boundary check)."""
        texts = ["text"] * 2048

        mock_embeddings = [MagicMock(embedding=[0.0] * 1536) for _ in texts]
        mock_response = MagicMock()
        mock_response.data = mock_embeddings
        mock_response.usage.total_tokens = 2048 * 5

        mock_openai_client.embeddings.create = AsyncMock(return_value=mock_response)

        adapter = OpenAIEmbeddingAdapter(config)
        result = await adapter.embed(texts)

        assert mock_openai_client.embeddings.create.call_count == 1
        assert len(result.vectors) == 2048
        # Single call means we know the token count
        assert result.total_tokens == 2048 * 5
