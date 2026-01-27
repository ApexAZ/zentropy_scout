"""Embedding provider module.

Exports:
    EmbeddingProvider: Abstract base class for embeddings
    EmbeddingResult: Result dataclass from embedding operations
    OpenAIEmbeddingAdapter: OpenAI implementation
"""

from app.providers.embedding.base import EmbeddingProvider, EmbeddingResult
from app.providers.embedding.mock_adapter import MockEmbeddingProvider
from app.providers.embedding.openai_adapter import OpenAIEmbeddingAdapter

__all__ = [
    "EmbeddingProvider",
    "EmbeddingResult",
    "MockEmbeddingProvider",
    "OpenAIEmbeddingAdapter",
]
