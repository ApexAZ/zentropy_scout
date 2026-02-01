"""Embedding storage service.

REQ-008 §6.5-6.6: Utilities for embedding storage and staleness detection.

Provides:
- Embedding type enums for type safety
- Source hash computation for staleness detection
- Freshness check for detecting stale embeddings
"""

import hashlib
from enum import Enum

# =============================================================================
# Embedding Type Enums
# =============================================================================


class PersonaEmbeddingType(str, Enum):
    """Types of persona embeddings.

    REQ-008 §6.3: Three embedding types per persona.

    Values:
        HARD_SKILLS: Technical skills with proficiency levels.
        SOFT_SKILLS: Soft skills (names only, no proficiency).
        LOGISTICS: Location, remote preference, exclusions.
    """

    HARD_SKILLS = "hard_skills"
    SOFT_SKILLS = "soft_skills"
    LOGISTICS = "logistics"


class JobEmbeddingType(str, Enum):
    """Types of job embeddings.

    REQ-008 §6.4: Two embedding types per job.

    Values:
        REQUIREMENTS: Required/preferred skills with experience levels.
        CULTURE: Company values and culture text.
    """

    REQUIREMENTS = "requirements"
    CULTURE = "culture"


# Union type for any embedding type
EmbeddingType = PersonaEmbeddingType | JobEmbeddingType


# =============================================================================
# Source Hash Computation
# =============================================================================


def compute_source_hash(source_text: str) -> str:
    """Compute SHA-256 hash of source text for staleness detection.

    REQ-008 §6.5: The source_hash column stores a hash of the text that was
    embedded. This allows detecting when embeddings are stale (source changed).

    WHY SHA-256:
    - Deterministic: same input always produces same hash
    - Fast: minimal overhead for staleness checks
    - Collision-resistant: different inputs produce different hashes

    Args:
        source_text: The text that will be/was embedded.

    Returns:
        64-character lowercase hex string (SHA-256 digest).
    """
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


# =============================================================================
# Freshness Check
# =============================================================================


def is_embedding_fresh(current_source_text: str, stored_hash: str) -> bool:
    """Check if an embedding is fresh (matches current source).

    REQ-008 §6.6: Compare stored hash with hash of current source text to
    detect when embeddings are stale and need regeneration.

    Args:
        current_source_text: The current text that would be embedded.
        stored_hash: The hash stored with the embedding.

    Returns:
        True if embedding is fresh (hashes match), False if stale.
    """
    if not stored_hash:
        return False
    return compute_source_hash(current_source_text) == stored_hash
