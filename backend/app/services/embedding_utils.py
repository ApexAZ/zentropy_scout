"""Shared embedding utilities for scoring services.

Common validation and helper functions used across embedding-based
scoring services (role_title_match, stretch_score, soft_skills_match).
"""


def validate_embeddings(
    embedding_a: list[float],
    embedding_b: list[float],
    max_dimensions: int,
) -> None:
    """Validate that two embeddings are non-empty, same-sized, and within bounds.

    Args:
        embedding_a: First embedding vector.
        embedding_b: Second embedding vector.
        max_dimensions: Maximum allowed dimensions.

    Raises:
        ValueError: If embeddings are empty, mismatched, or exceed max dimensions.
    """
    if len(embedding_a) == 0 or len(embedding_b) == 0:
        msg = "Embeddings cannot be empty"
        raise ValueError(msg)

    if len(embedding_a) != len(embedding_b):
        msg = (
            f"Embedding dimensions must match: {len(embedding_a)} vs {len(embedding_b)}"
        )
        raise ValueError(msg)

    if len(embedding_a) > max_dimensions or len(embedding_b) > max_dimensions:
        msg = f"Embeddings exceed maximum dimensions of {max_dimensions}"
        raise ValueError(msg)
