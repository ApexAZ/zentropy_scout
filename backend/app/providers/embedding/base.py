"""Abstract base class for embedding providers.

REQ-009 §5.1: EmbeddingProvider abstract interface.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


class EmbeddingProvider(ABC):
    """Abstract interface for embedding providers.

    WHY ABC:
    - Enforces consistent interface across providers
    - Enables dependency injection for testing
    - Allows swapping providers without code changes
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize with provider configuration.

        Args:
            config: Provider configuration including API keys.
        """
        self.config = config

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: The text to embed.

        Returns:
            List of floats representing the embedding vector.
        """
        ...

    @abstractmethod
    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.
            batch_size: Number of texts to process per API call.

        Returns:
            List of embedding vectors, one per input text.
        """
        ...
