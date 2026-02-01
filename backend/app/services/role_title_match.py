"""Role title match calculation for Fit Score.

REQ-008 §4.5: Role Title Match component (10% of Fit Score).

Compares user's current role and work history titles against job title.
Uses two-step matching:
1. Exact match (after normalization) returns 100
2. Semantic similarity via embeddings, scaled to 0-100

Key formula for semantic matching:
    score = (cosine_similarity + 1) * 50

This scales cosine similarity from [-1, 1] to score [0, 100].
"""

import re

from app.services.fit_score import FIT_NEUTRAL_SCORE
from app.services.soft_skills_match import cosine_similarity

# =============================================================================
# Constants
# =============================================================================

# Maximum work history entries to prevent DoS
_MAX_WORK_HISTORY = 500

# Maximum embedding dimensions (same as soft_skills_match)
_MAX_EMBEDDING_DIMENSIONS = 5000

# Maximum title length to prevent regex DoS on oversized strings
_MAX_TITLE_LENGTH = 500

# =============================================================================
# Title Normalization (REQ-008 §4.5.2)
# =============================================================================

# Seniority prefix patterns (normalized to standard form)
_SENIORITY_PREFIXES: dict[str, str] = {
    "sr.": "senior",
    "sr": "senior",
    "lead": "senior",
    "principal": "senior",
    "staff": "senior",
    "jr.": "junior",
    "jr": "junior",
    "associate": "junior",
    "entry-level": "junior",
}

# Role title synonyms (normalized to canonical form)
_ROLE_SYNONYMS: dict[str, str] = {
    "software developer": "software engineer",
    "sde": "software engineer",
    "swe": "software engineer",
    "dev": "developer",
    "pm": "product manager",
}


def normalize_title(title: str) -> str:
    """Normalize job title for matching.

    REQ-008 §4.5.2: Title Normalization.

    Handles:
    - Case normalization (lowercase)
    - Whitespace normalization (strip and collapse multiple spaces)
    - Seniority prefix normalization (Sr. → senior, Jr. → junior, etc.)
    - Role synonym normalization (SDE → software engineer, etc.)

    Args:
        title: Raw job title.

    Returns:
        Normalized title for comparison.
    """
    if not title:
        return ""

    # Truncate oversized titles to prevent regex DoS
    if len(title) > _MAX_TITLE_LENGTH:
        title = title[:_MAX_TITLE_LENGTH]

    # Lowercase and strip
    normalized = title.lower().strip()

    # Collapse multiple spaces to single space
    normalized = re.sub(r"\s+", " ", normalized)

    # Normalize seniority prefixes
    for prefix, replacement in _SENIORITY_PREFIXES.items():
        # Match at start of string, followed by space or dot
        pattern = rf"^{re.escape(prefix)}\.?\s+"
        if re.match(pattern, normalized):
            normalized = re.sub(pattern, f"{replacement} ", normalized)
            break

    # Apply role synonyms (check full match and partial)
    for synonym, canonical in _ROLE_SYNONYMS.items():
        if normalized == synonym:
            return canonical
        # Replace as substring for compound titles
        normalized = re.sub(
            rf"\b{re.escape(synonym)}\b",
            canonical,
            normalized,
        )

    return normalized


# =============================================================================
# Role Title Score Calculation (REQ-008 §4.5)
# =============================================================================


def calculate_role_title_score(
    current_role: str | None,
    work_history_titles: list[str] | None,
    job_title: str | None,
    user_titles_embedding: list[float] | None,
    job_title_embedding: list[float] | None,
) -> float:
    """Calculate role title match score (0-100).

    REQ-008 §4.5: Role Title Match (10% of Fit Score).

    Uses two-step matching:
    1. Exact match (after normalization) → returns 100
    2. Semantic similarity via embeddings → scaled to 0-100

    Args:
        current_role: User's current job title. None if not set.
        work_history_titles: List of past job titles from work history.
        job_title: Target job's title. None if not specified.
        user_titles_embedding: Pre-computed embedding of user's titles
            (current + work history joined). None if not available.
        job_title_embedding: Pre-computed embedding of job title.
            None if not available.

    Returns:
        Role title score 0-100:
        - 100: Exact match (after normalization)
        - 70: Neutral (missing data)
        - 0-100: Semantic similarity score

    Raises:
        ValueError: If embeddings have different dimensions or exceed max size,
            or if work history exceeds max size.
    """
    # Normalize inputs
    work_history = work_history_titles if work_history_titles is not None else []

    # Validate work history size
    if len(work_history) > _MAX_WORK_HISTORY:
        msg = f"Work history exceeds maximum size of {_MAX_WORK_HISTORY}"
        raise ValueError(msg)

    # Collect and normalize user titles (filter empty/whitespace-only)
    user_titles: list[str] = []
    if current_role and current_role.strip():
        user_titles.append(current_role.strip())
    for title in work_history:
        if title and title.strip():
            user_titles.append(title.strip())

    # Handle missing data
    if not user_titles or not job_title or not job_title.strip():
        return FIT_NEUTRAL_SCORE

    # Normalize all titles
    normalized_user_titles = [normalize_title(t) for t in user_titles]
    normalized_job_title = normalize_title(job_title)

    # Step 1: Check for exact match (after normalization)
    if normalized_job_title in normalized_user_titles:
        return 100.0

    # Step 2: Semantic similarity via embeddings
    # If embeddings not available, return neutral
    if user_titles_embedding is None or job_title_embedding is None:
        return FIT_NEUTRAL_SCORE

    # Validate embeddings
    if len(user_titles_embedding) == 0 or len(job_title_embedding) == 0:
        msg = "Embeddings cannot be empty"
        raise ValueError(msg)

    if len(user_titles_embedding) != len(job_title_embedding):
        msg = (
            f"Embedding dimensions must match: "
            f"{len(user_titles_embedding)} vs {len(job_title_embedding)}"
        )
        raise ValueError(msg)

    if (
        len(user_titles_embedding) > _MAX_EMBEDDING_DIMENSIONS
        or len(job_title_embedding) > _MAX_EMBEDDING_DIMENSIONS
    ):
        msg = f"Embeddings exceed maximum dimensions of {_MAX_EMBEDDING_DIMENSIONS}"
        raise ValueError(msg)

    # Calculate cosine similarity and scale to 0-100
    similarity = cosine_similarity(user_titles_embedding, job_title_embedding)

    # Scale from [-1, 1] to [0, 100]
    # cosine_similarity already clamps to [-1, 1], so result is always [0, 100]
    return (similarity + 1) * 50
