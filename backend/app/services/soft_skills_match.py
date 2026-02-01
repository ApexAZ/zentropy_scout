"""Soft skills match calculation for Fit Score.

REQ-008 §4.3: Soft Skills Match component (15% of Fit Score).

Uses embedding cosine similarity to match persona soft skills against
job soft skills. Embeddings capture semantic meaning, so "Leadership"
and "Team Management" are recognized as related even without exact match.

Key formula:
    score = (cosine_similarity + 1) * 50

This scales cosine similarity from [-1, 1] to score [0, 100]:
| Cosine | Score | Interpretation |
|--------|-------|----------------|
| 1.0    | 100   | Perfect match  |
| 0.5    | 75    | Good match     |
| 0.0    | 50    | No correlation |
| -0.5   | 25    | Poor match     |
| -1.0   | 0     | Opposite       |
"""

import math

from app.services.fit_score import FIT_NEUTRAL_SCORE

# =============================================================================
# Constants
# =============================================================================

# Maximum embedding dimensions to prevent DoS via oversized vectors
# OpenAI text-embedding-3-small uses 1536, allow up to 2x for safety
_MAX_EMBEDDING_DIMENSIONS = 5000


# =============================================================================
# Cosine Similarity (REQ-008 §4.3.1)
# =============================================================================


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    REQ-008 §4.3.1: Used for semantic matching of soft skills.

    Cosine similarity measures the angle between vectors, ignoring magnitude.
    This makes it ideal for comparing embeddings where direction (meaning)
    matters more than scale.

    Args:
        vec1: First embedding vector.
        vec2: Second embedding vector.

    Returns:
        Similarity in range [-1.0, 1.0]:
        - 1.0: Identical direction (same meaning)
        - 0.0: Orthogonal (unrelated)
        - -1.0: Opposite direction (opposite meaning)

    Raises:
        ValueError: If vectors have different lengths or are empty.
    """
    if len(vec1) != len(vec2):
        msg = f"Vectors must have same length: {len(vec1)} vs {len(vec2)}"
        raise ValueError(msg)

    if len(vec1) == 0:
        msg = "Vectors cannot be empty"
        raise ValueError(msg)

    # Validate vectors contain finite values (no NaN/Inf)
    # Defense-in-depth: OpenAI embeddings should never contain these,
    # but corrupt data could cause undefined behavior in calculations
    if not all(math.isfinite(x) for x in vec1) or not all(
        math.isfinite(x) for x in vec2
    ):
        msg = "Vectors must contain finite values (no NaN or Inf)"
        raise ValueError(msg)

    # Calculate dot product and magnitudes
    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    # Handle zero vectors (no direction)
    # Zero vector is orthogonal to everything, return 0
    if norm1 == 0 or norm2 == 0:
        return 0.0

    result = dot_product / (norm1 * norm2)

    # Clamp to [-1, 1] to handle floating point precision issues
    # Mathematically, cosine similarity is always in this range,
    # but floating point arithmetic can produce values like 1.0000000002
    return max(-1.0, min(1.0, result))


# =============================================================================
# Soft Skills Score Calculation (REQ-008 §4.3)
# =============================================================================


def calculate_soft_skills_score(
    persona_soft_embedding: list[float] | None,
    job_soft_embedding: list[float] | None,
) -> float:
    """Calculate soft skills match score (0-100).

    REQ-008 §4.3: Soft Skills Match (15% of Fit Score).

    Uses embedding cosine similarity to match persona soft skills against
    job soft skills. Pre-computed embeddings are expected as input.

    Score formula:
        score = (cosine_similarity + 1) * 50

    Args:
        persona_soft_embedding: Pre-computed embedding of persona soft skills.
            Generated from soft skill names joined by " | ".
            None if persona has no soft skills.
        job_soft_embedding: Pre-computed embedding of job soft skills.
            Generated from extracted soft skill names.
            None if job has no soft skills.

    Returns:
        Soft skills score 0-100:
        - 100: Perfect semantic match
        - 70: Neutral (missing data)
        - 50: No correlation (orthogonal embeddings)
        - 0: Opposite (extremely rare with real embeddings)

    Raises:
        ValueError: If embeddings have different dimensions or exceed max size.
    """
    # REQ-008 §9.1: Missing data returns neutral score (70)
    if persona_soft_embedding is None or job_soft_embedding is None:
        return FIT_NEUTRAL_SCORE

    # Validate embedding dimensions
    if len(persona_soft_embedding) == 0 or len(job_soft_embedding) == 0:
        msg = "Embeddings cannot be empty"
        raise ValueError(msg)

    if len(persona_soft_embedding) != len(job_soft_embedding):
        msg = (
            f"Embedding dimensions must match: "
            f"{len(persona_soft_embedding)} vs {len(job_soft_embedding)}"
        )
        raise ValueError(msg)

    # Defensive size limit to prevent DoS (check both embeddings explicitly)
    if (
        len(persona_soft_embedding) > _MAX_EMBEDDING_DIMENSIONS
        or len(job_soft_embedding) > _MAX_EMBEDDING_DIMENSIONS
    ):
        msg = f"Embeddings exceed maximum dimensions of {_MAX_EMBEDDING_DIMENSIONS}"
        raise ValueError(msg)

    # Calculate cosine similarity between embeddings
    similarity = cosine_similarity(persona_soft_embedding, job_soft_embedding)

    # Scale from [-1, 1] to [0, 100]
    # REQ-008 §4.3.1: score = (cosine + 1) * 50
    return (similarity + 1) * 50
