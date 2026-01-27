"""Mock embedding provider for testing.

REQ-009 §9.2: MockEmbeddingProvider enables unit testing without hitting real APIs.
"""

from typing import Any

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock provider for embedding tests.

    WHY MOCK:
    - Unit tests shouldn't hit real APIs (cost, speed, flakiness)
    - Enables deterministic testing
    - Consistent vector dimensions for database tests

    Attributes:
        calls: Record of all method invocations for test assertions.
    """

    # Match OpenAI text-embedding-3-small dimensions
    MOCK_DIMENSIONS = 1536

    def __init__(self) -> None:
        """Initialize mock embedding provider.

        Note: Does not call super().__init__() - we don't need a config for mock.
        """
        self.calls: list[dict[str, Any]] = []

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate mock embeddings.

        Returns fixed-value vectors for deterministic testing.
        Each vector is filled with 0.1 values.

        Args:
            texts: List of strings to embed.

        Returns:
            EmbeddingResult with mock vectors.
        """
        self.calls.append(
            {
                "method": "embed",
                "texts": texts,
            }
        )

        # Generate mock vectors (all 0.1 values, same length as real embeddings)
        vectors = [[0.1] * self.MOCK_DIMENSIONS for _ in texts]

        return EmbeddingResult(
            vectors=vectors,
            model="mock-embedding-model",
            dimensions=self.MOCK_DIMENSIONS,
            total_tokens=len(texts) * 10,  # Rough estimate
        )

    @property
    def dimensions(self) -> int:
        """Return the mock embedding dimensions.

        Returns:
            1536 (matching text-embedding-3-small).
        """
        return self.MOCK_DIMENSIONS

    def assert_embedded(self, text: str) -> None:
        """Test helper to verify a text was embedded.

        Args:
            text: The text that should have been embedded.

        Raises:
            AssertionError: If the text was not embedded.
        """
        all_texts = []
        for call in self.calls:
            all_texts.extend(call["texts"])
        assert text in all_texts, f"Expected '{text}' to be embedded, got {all_texts}"
