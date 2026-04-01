"""Google Gemini embedding adapter.

REQ-028 §7: GeminiEmbeddingAdapter using google.genai SDK.

WHY GEMINI FOR EMBEDDINGS:
- Eliminates OpenAI API key dependency when using Claude + Gemini
- text-embedding-004 offers competitive quality at 768 dimensions
- Same SDK (google-genai) already used for Gemini LLM adapter

Coordinates with:
  - providers/embedding/base.py (EmbeddingProvider, EmbeddingResult)
  - providers/errors.py (ProviderError)
  - providers/gemini_errors.py (classify_gemini_error)
  - providers/config.py (ProviderConfig — TYPE_CHECKING only)

Called by: providers/factory.py (GeminiEmbeddingAdapter).
"""

from typing import TYPE_CHECKING, cast

from google import genai

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult
from app.providers.errors import ProviderError
from app.providers.gemini_errors import classify_gemini_error

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


# Gemini embed_content supports up to 100 content items per request
MAX_BATCH_SIZE = 100


class GeminiEmbeddingAdapter(EmbeddingProvider):
    """Google Gemini adapter for text embeddings.

    Uses the unified google-genai SDK (same as Gemini LLM adapter).
    Model: text-embedding-004 producing 768-dimensional vectors.
    """

    @property
    def provider_name(self) -> str:
        """Return 'gemini' for pricing lookup and usage tracking."""
        return "gemini"

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize Gemini embedding adapter.

        Args:
            config: Provider configuration with Google API key.
        """
        super().__init__(config)
        self.client = genai.Client(api_key=config.google_api_key)
        self._model = config.embedding_model
        self._dimensions = config.embedding_dimensions

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using Gemini.

        Handles batching transparently — chunks into 100-text batches
        if the input exceeds the Gemini API limit.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult with vectors in same order as input.

        Raises:
            ProviderError: On API failure (classified by error type).
        """
        if not texts:
            return EmbeddingResult(
                vectors=[],
                model=self._model,
                dimensions=self._dimensions,
                total_tokens=0,
            )

        if len(texts) > MAX_BATCH_SIZE:
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
        """Embed a single batch of texts (up to 100).

        Args:
            texts: List of texts to embed (max 100).

        Returns:
            EmbeddingResult with vectors.
        """
        try:
            response = await self.client.aio.models.embed_content(
                model=self._model,
                contents=cast(list, texts),
            )
        except Exception as e:
            raise classify_gemini_error(e) from e

        if not response.embeddings:
            raise ProviderError("Gemini returned no embeddings")

        vectors: list[list[float]] = [emb.values or [] for emb in response.embeddings]

        # Gemini reports billable_character_count, not tokens.
        # Estimate tokens as chars // 4 for metering compatibility.
        total_tokens: int
        if (
            response.metadata
            and response.metadata.billable_character_count is not None
            and response.metadata.billable_character_count > 0
        ):
            total_tokens = response.metadata.billable_character_count // 4
        else:
            # Fallback: estimate from text lengths
            total_tokens = sum(len(t) for t in texts) // 4

        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            dimensions=self._dimensions,
            total_tokens=total_tokens,
        )

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions (768 for text-embedding-004)."""
        return self._dimensions
