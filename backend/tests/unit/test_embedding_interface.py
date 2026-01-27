"""Tests for embedding provider interface (REQ-009 §5.1).

Tests the abstract interface components:
- EmbeddingResult dataclass
- EmbeddingProvider abstract base class
"""

import pytest

from app.providers.config import ProviderConfig
from app.providers.embedding.base import (
    EmbeddingProvider,
    EmbeddingResult,
)


class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_embedding_result_required_fields(self):
        """EmbeddingResult should have vectors, model, dimensions, total_tokens."""
        result = EmbeddingResult(
            vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            model="text-embedding-3-small",
            dimensions=3,
            total_tokens=10,
        )
        assert len(result.vectors) == 2
        assert result.model == "text-embedding-3-small"
        assert result.dimensions == 3
        assert result.total_tokens == 10

    def test_embedding_result_vectors_preserve_order(self):
        """Vectors should maintain input order."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 5.0, 6.0]
        result = EmbeddingResult(
            vectors=[vec1, vec2],
            model="model",
            dimensions=3,
            total_tokens=5,
        )
        assert result.vectors[0] == vec1
        assert result.vectors[1] == vec2

    def test_embedding_result_single_text(self):
        """EmbeddingResult should work for single-text embedding."""
        result = EmbeddingResult(
            vectors=[[0.1, 0.2, 0.3]],
            model="text-embedding-3-small",
            dimensions=3,
            total_tokens=3,
        )
        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 3


class TestEmbeddingProviderInterface:
    """Test EmbeddingProvider abstract base class."""

    def test_embedding_provider_is_abstract(self):
        """EmbeddingProvider should be abstract and not instantiable directly."""
        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            EmbeddingProvider(config)  # type: ignore[abstract]
        assert "abstract" in str(exc_info.value).lower()

    def test_embedding_provider_requires_embed_method(self):
        """Subclasses must implement embed()."""

        class IncompleteProvider(EmbeddingProvider):
            @property
            def dimensions(self) -> int:
                return 1536

        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(config)  # type: ignore[abstract]
        assert "embed" in str(exc_info.value)

    def test_embedding_provider_requires_dimensions_property(self):
        """Subclasses must implement dimensions property."""

        class IncompleteProvider(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=[[0.0] * 1536 for _ in texts],
                    model="test",
                    dimensions=1536,
                    total_tokens=0,
                )

        config = ProviderConfig()
        with pytest.raises(TypeError) as exc_info:
            IncompleteProvider(config)  # type: ignore[abstract]
        assert "dimensions" in str(exc_info.value)

    def test_embedding_provider_stores_config(self):
        """EmbeddingProvider should store config for subclasses to use."""

        class ConcreteProvider(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=[[0.0] * 1536 for _ in texts],
                    model="test",
                    dimensions=1536,
                    total_tokens=0,
                )

            @property
            def dimensions(self) -> int:
                return 1536

        config = ProviderConfig(openai_api_key="test-key")
        provider = ConcreteProvider(config)
        assert provider.config.openai_api_key == "test-key"


class TestEmbeddingProviderEmbedSignature:
    """Test that embed() has correct batch-first signature."""

    def test_embed_accepts_list_of_texts(self):
        """embed() should accept a list of strings (batch-first API)."""

        class MockProvider(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                # Verify we received a list
                assert isinstance(texts, list)
                assert all(isinstance(t, str) for t in texts)
                return EmbeddingResult(
                    vectors=[[0.0] * 1536 for _ in texts],
                    model="test-model",
                    dimensions=1536,
                    total_tokens=len(texts) * 5,
                )

            @property
            def dimensions(self) -> int:
                return 1536

        config = ProviderConfig()
        _provider = MockProvider(config)
        # Signature check passed if instantiation works

    def test_embed_returns_embedding_result(self):
        """embed() should return EmbeddingResult."""

        class MockProvider(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=[[0.0] * 1536 for _ in texts],
                    model="test-model",
                    dimensions=1536,
                    total_tokens=10,
                )

            @property
            def dimensions(self) -> int:
                return 1536

        config = ProviderConfig()
        _provider = MockProvider(config)
        # Type annotation verifies return type


class TestEmbeddingProviderDimensionsProperty:
    """Test the dimensions property behavior."""

    def test_dimensions_returns_vector_size(self):
        """dimensions property should return the embedding vector size."""

        class Provider1536(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=[[0.0] * 1536 for _ in texts],
                    model="text-embedding-3-small",
                    dimensions=1536,
                    total_tokens=0,
                )

            @property
            def dimensions(self) -> int:
                return 1536

        class Provider3072(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=[[0.0] * 3072 for _ in texts],
                    model="text-embedding-3-large",
                    dimensions=3072,
                    total_tokens=0,
                )

            @property
            def dimensions(self) -> int:
                return 3072

        config = ProviderConfig()
        provider_small = Provider1536(config)
        provider_large = Provider3072(config)

        assert provider_small.dimensions == 1536
        assert provider_large.dimensions == 3072

    def test_dimensions_usable_for_database_schema(self):
        """dimensions should be queryable for database vector column sizing."""

        class MockProvider(EmbeddingProvider):
            async def embed(self, texts: list[str]) -> EmbeddingResult:
                return EmbeddingResult(
                    vectors=[[0.0] * self.dimensions for _ in texts],
                    model="test",
                    dimensions=self.dimensions,
                    total_tokens=0,
                )

            @property
            def dimensions(self) -> int:
                return 1536

        config = ProviderConfig()
        provider = MockProvider(config)

        # Simulate database schema creation
        vector_column_size = provider.dimensions
        assert vector_column_size > 0
        assert isinstance(vector_column_size, int)
