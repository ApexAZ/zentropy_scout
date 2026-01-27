"""Abstract base class and types for embedding providers.

REQ-009 §5.1: EmbeddingProvider abstract interface with batch-first API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.providers.config import ProviderConfig


@dataclass
class EmbeddingResult:
    """Result of embedding operation.

    WHY DATACLASS: Simple data container with clear fields.
    Enables type checking and IDE autocomplete.

    Attributes:
        vectors: One embedding vector per input text, in same order.
        model: Model identifier used for embedding.
        dimensions: Number of dimensions in each vector.
        total_tokens: Total tokens processed across all inputs.
    """

    vectors: list[list[float]]
    model: str
    dimensions: int
    total_tokens: int


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.

    WHY SEPARATE FROM LLM PROVIDER:
    - Different API patterns (batch-oriented vs conversational)
    - Different providers may be optimal (OpenAI embeddings are excellent)
    - Embeddings are stateless; LLM may need conversation context
    """

    def __init__(self, config: "ProviderConfig") -> None:
        """Initialize with provider configuration.

        Args:
            config: Provider configuration including API keys.
        """
        self.config = config

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        WHY BATCH BY DEFAULT:
        - Embedding APIs are optimized for batch calls
        - Reduces round trips and latency
        - Single-text embedding is just batch of 1: embed(["text"])

        Args:
            texts: List of strings to embed.

        Returns:
            EmbeddingResult with vectors in same order as input.

        Raises:
            ProviderError: On API failure after retries.
        """
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimensions.

        WHY PROPERTY: Database schema needs to know vector size
        at table creation time. This makes it queryable.

        Returns:
            Number of dimensions in the embedding vectors (e.g., 1536).
        """
        ...
