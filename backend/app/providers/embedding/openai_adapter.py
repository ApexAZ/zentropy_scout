"""OpenAI embedding adapter.

REQ-009 §5.2: OpenAI Embedding Adapter.
"""

from typing import TYPE_CHECKING

from app.providers.embedding.base import EmbeddingProvider

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


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
        # Actual client initialization will be added in §5.2

    async def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI.

        Implementation will be added in §5.2.
        """
        raise NotImplementedError("OpenAIEmbeddingAdapter.embed() not yet implemented")

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings for batch using OpenAI.

        Implementation will be added in §5.2.
        """
        raise NotImplementedError(
            "OpenAIEmbeddingAdapter.embed_batch() not yet implemented"
        )
