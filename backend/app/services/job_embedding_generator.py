"""Job embedding generation service.

REQ-008 §6.4: Generate embeddings for job posting data.

Generates two embedding types from job posting data:
1. requirements: Required + preferred skills with experience levels
2. culture: Company values, team description, benefits

Called on: Job ingestion, Job extraction update.

Key Principle (REQ-008 §6.1):
    Culture embedding must be SEPARATED from requirements to avoid
    technical keywords polluting soft skill similarity matches.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# =============================================================================
# Constants
# =============================================================================

EMBEDDING_DIMENSIONS = 1536  # OpenAI text-embedding-3-small dimensions


# =============================================================================
# Type Definitions
# =============================================================================


class ExtractedSkillLike(Protocol):
    """Protocol for extracted skill objects (avoids tight coupling to ORM model)."""

    skill_name: str
    skill_type: str
    is_required: bool
    years_requested: int | None


class JobPostingLike(Protocol):
    """Protocol for job posting objects (avoids tight coupling to ORM model)."""

    id: uuid.UUID
    extracted_skills: list[ExtractedSkillLike]
    culture_text: str | None
    years_experience_min: int | None
    years_experience_max: int | None
    updated_at: datetime


# Type alias for embedding function signature
EmbedFunction = Callable[[str], Awaitable[list[list[float]]]]


# =============================================================================
# Result Dataclasses
# =============================================================================


@dataclass
class JobEmbeddingData:
    """Single embedding with its source text.

    Attributes:
        vector: The 1536-dimensional embedding vector.
        source_text: The text that was embedded (for debugging/auditing).
    """

    vector: list[float]
    source_text: str


@dataclass
class JobEmbeddingsResult:
    """Result of generating all job embeddings.

    REQ-008 §6.4: Two embedding types per job.

    Attributes:
        job_id: UUID of the job posting these embeddings belong to.
        requirements: Embedding for skills/experience requirements.
        culture: Embedding for company culture (or neutral if missing).
        version: Timestamp for staleness detection (from job.updated_at).
        model_name: Name of the embedding model used.
    """

    job_id: uuid.UUID
    requirements: JobEmbeddingData
    culture: JobEmbeddingData
    version: datetime
    model_name: str


# =============================================================================
# Text Building Functions
# =============================================================================


def build_requirements_text(
    skills: list[ExtractedSkillLike],
    years_min: int | None,
    years_max: int | None,
) -> str:
    """Build embedding text from job requirements.

    REQ-008 §6.4: Format includes required skills with years, preferred skills,
    and overall experience range.

    Args:
        skills: List of extracted skill objects.
        years_min: Minimum years of experience required.
        years_max: Maximum years of experience required.

    Returns:
        Formatted multi-line text for embedding.
        Example:
            Required: Python (5+ years) | SQL | Kubernetes (3+ years)
            Preferred: Terraform | Go
            Experience: 5-8 years
    """
    if not skills:
        return ""

    # Separate required and preferred skills
    required_skills = [s for s in skills if s.is_required]
    preferred_skills = [s for s in skills if not s.is_required]

    # Format required skills: include years if specified
    required_parts = []
    for skill in required_skills:
        if skill.years_requested:
            required_parts.append(
                f"{skill.skill_name} ({skill.years_requested}+ years)"
            )
        else:
            required_parts.append(skill.skill_name)

    required_text = " | ".join(required_parts) if required_parts else "None"

    # Format preferred skills: names only
    preferred_text = (
        " | ".join(s.skill_name for s in preferred_skills)
        if preferred_skills
        else "None"
    )

    # Format experience range
    if years_min is not None and years_max is not None:
        experience_text = f"{years_min}-{years_max} years"
    elif years_min is not None:
        experience_text = f"{years_min}+ years"
    elif years_max is not None:
        experience_text = f"Up to {years_max} years"
    else:
        experience_text = "Not specified"

    return f"""Required: {required_text}
Preferred: {preferred_text}
Experience: {experience_text}"""


def build_culture_text(culture_text: str | None) -> str:
    """Build embedding text from job culture.

    REQ-008 §6.4: Culture text is used directly if present.

    CRITICAL (REQ-008 §6.1): This text must come from LLM extraction
    of the "About Us" / culture sections ONLY. Never embed the full
    description — technical keywords would pollute soft skill matching.

    Args:
        culture_text: Pre-extracted culture text from Scouter agent.

    Returns:
        The culture text if valid, empty string otherwise.
    """
    if not culture_text or not culture_text.strip():
        return ""

    return culture_text


def get_neutral_embedding() -> list[float]:
    """Return a neutral (zero) embedding vector.

    REQ-008 §6.4: Used when culture text is missing.

    WHY ZERO VECTOR:
    - Cosine similarity with any vector = 0 (orthogonal)
    - This gives a neutral soft skills score (50), not a penalty
    - Better than embedding random text or the full description

    Returns:
        A 1536-dimensional zero vector.
    """
    return [0.0] * EMBEDDING_DIMENSIONS


# =============================================================================
# Main Generation Function
# =============================================================================


async def generate_job_embeddings(
    job: JobPostingLike,
    embed_fn: EmbedFunction,
    model_name: str = "text-embedding-3-small",
) -> JobEmbeddingsResult:
    """Generate all embeddings for a job posting.

    REQ-008 §6.4: Called on job ingestion and extraction updates.

    Args:
        job: Job posting object with extracted skills and culture text.
        embed_fn: Async function that takes text and returns embedding vector.
                  Signature: async def embed(text: str) -> list[list[float]]
        model_name: Name of embedding model (for tracking).

    Returns:
        JobEmbeddingsResult with both embedding types.
    """
    # Build text for each embedding type
    requirements_text = build_requirements_text(
        job.extracted_skills,
        job.years_experience_min,
        job.years_experience_max,
    )
    culture_text = build_culture_text(job.culture_text)

    # Generate requirements embedding
    # WHY SEPARATE CALLS: Requirements and culture have distinct semantic content.
    # Combining them would pollute the vector space (REQ-008 §6.1 principle).
    if requirements_text:
        requirements_result = await embed_fn(requirements_text)
        requirements_vector = requirements_result[0]
    else:
        requirements_vector = get_neutral_embedding()

    # Generate culture embedding (or use neutral if missing)
    if culture_text:
        culture_result = await embed_fn(culture_text)
        culture_vector = culture_result[0]
    else:
        # WHY NEUTRAL: Missing culture should not penalize soft skill matching.
        # Cosine similarity of neutral vector = 0, giving 50% score (neutral).
        culture_vector = get_neutral_embedding()

    return JobEmbeddingsResult(
        job_id=job.id,
        requirements=JobEmbeddingData(
            vector=requirements_vector,
            source_text=requirements_text,
        ),
        culture=JobEmbeddingData(
            vector=culture_vector,
            source_text=culture_text,
        ),
        version=job.updated_at,
        model_name=model_name,
    )
