"""OpenAI embedding adapter.

REQ-009 §5.2: OpenAI Embedding Adapter.

WHY OPENAI FOR EMBEDDINGS:
- text-embedding-3-small has excellent quality/cost ratio
- 1536 dimensions fit well with pgvector
- Reliable API with good batching support
"""

from typing import TYPE_CHECKING

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig

# Default model per REQ-009 §5.3
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536


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
        # Full implementation will be added in §5.2
        self._model = DEFAULT_EMBEDDING_MODEL
        self._dimensions = DEFAULT_EMBEDDING_DIMENSIONS

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using OpenAI.

        Full implementation will be added in §5.2.
        """
        raise NotImplementedError("OpenAIEmbeddingAdapter.embed() not yet implemented")

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions (1536 for text-embedding-3-small)."""
        return self._dimensions
