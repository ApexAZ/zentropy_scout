"""OpenAI embedding adapter.

REQ-009 §5.2: OpenAI Embedding Adapter with batching support.

WHY OPENAI FOR EMBEDDINGS (even when using Claude for LLM):
- text-embedding-3-small has excellent quality/cost ratio
- Well-documented, stable API
- Good batch support (up to 2048 texts)
- Anthropic doesn't offer embeddings (as of early 2025)
"""

from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


# OpenAI API limits
MAX_BATCH_SIZE = 2048


class OpenAIEmbeddingAdapter(EmbeddingProvider):
    """OpenAI adapter for text embeddings.

    WHY SEPARATE ADAPTER:
    - Isolates provider-specific code
    - Easy to test with mocks
    - Clear separation of concerns
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize OpenAI embedding adapter.

        Args:
            config: Provider configuration with OpenAI API key.
        """
        super().__init__(config)
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self._model = config.embedding_model
        self._dimensions = config.embedding_dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using OpenAI.

        WHY BATCH INTERNALLY:
        - OpenAI has a limit of 2048 texts per API call
        - We handle chunking transparently for the caller
        - Single-text embedding is just batch of 1

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult with vectors in same order as input.
        """
        if len(texts) > MAX_BATCH_SIZE:
            # Chunk into batches
            all_vectors: list[list[float]] = []
            for i in range(0, len(texts), MAX_BATCH_SIZE):
                batch = texts[i : i + MAX_BATCH_SIZE]
                batch_result = await self._embed_batch(batch)
                all_vectors.extend(batch_result.vectors)

            return EmbeddingResult(
                vectors=all_vectors,
                model=self._model,
                dimensions=self._dimensions,
                total_tokens=-1,  # Unknown for chunked requests
            )

        return await self._embed_batch(texts)

    async def _embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """Embed a single batch of texts (up to 2048).

        Args:
            texts: List of texts to embed (max 2048).

        Returns:
            EmbeddingResult with vectors.
        """
        response = await self.client.embeddings.create(
            model=self._model,
            input=texts,
        )

        # Extract vectors from response, maintaining order
        vectors = [item.embedding for item in response.data]

        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            dimensions=self._dimensions,
            total_tokens=response.usage.total_tokens,
        )

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions (e.g., 1536 for text-embedding-3-small)."""
        return self._dimensions
