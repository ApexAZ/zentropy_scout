"""Batch scoring service for efficient job-persona matching.

REQ-008 §10.1: Batch Scoring — score multiple jobs efficiently.

Key optimizations:
1. Load persona embeddings once (not per job)
2. Generate job embeddings in batch (single API call instead of N calls)
3. Score sequentially (CPU-bound calculation, no benefit from async)

Called by: Strategist agent when Scouter discovers many jobs at once.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from app.services.experience_level import calculate_experience_score
from app.services.fit_score import FitScoreResult, calculate_fit_score
from app.services.hard_skills_match import (
    JobSkillInput,
    PersonaSkillInput,
    calculate_hard_skills_score,
)
from app.services.job_embedding_generator import (
    build_culture_text,
    get_neutral_embedding,
)
from app.services.location_logistics import calculate_logistics_score
from app.services.persona_embedding_generator import PersonaEmbeddingsResult
from app.services.role_title_match import calculate_role_title_score
from app.services.soft_skills_match import calculate_soft_skills_score
from app.services.stretch_score import (
    StretchScoreResult,
    calculate_growth_trajectory,
    calculate_stretch_score,
    calculate_target_role_alignment,
    calculate_target_skills_exposure,
)

# =============================================================================
# Constants
# =============================================================================

# Maximum batch size to prevent resource exhaustion (DoS protection)
# REQ-008 §10.1: Reasonable limit for batch processing
_MAX_BATCH_SIZE = 500

# Expected embedding dimensions (text-embedding-3-small)
_EXPECTED_EMBEDDING_DIMENSIONS = 1536


# =============================================================================
# Type Definitions (Protocols for duck typing)
# =============================================================================

# Note: list[Any] is used in Protocol definitions because skill objects
# may come from different sources (ORM models, DTOs, test mocks) with
# varying attribute implementations. The actual attributes are validated
# by duck typing when accessed in helper functions.


class SkillLike(Protocol):
    """Protocol for persona skill objects."""

    skill_name: str
    skill_type: str
    proficiency: str


class ExtractedSkillLike(Protocol):
    """Protocol for job extracted skill objects."""

    skill_name: str
    skill_type: str
    is_required: bool
    years_requested: int | None


class PersonaLike(Protocol):
    """Protocol for persona objects."""

    id: uuid.UUID
    skills: list[Any]
    years_experience: int | None
    current_role: str | None
    target_roles: list[str]
    target_skills: list[str]
    remote_preference: str
    commutable_cities: list[str]


class JobPostingLike(Protocol):
    """Protocol for job posting objects."""

    id: uuid.UUID
    job_title: str
    extracted_skills: list[Any]
    culture_text: str | None
    years_experience_min: int | None
    years_experience_max: int | None
    work_model: str | None
    location: str | None


class EmbeddingResultLike(Protocol):
    """Protocol for embedding results."""

    vectors: list[list[float]]
    model: str
    dimensions: int
    total_tokens: int


class EmbeddingProviderLike(Protocol):
    """Protocol for embedding providers."""

    async def embed(self, texts: list[str]) -> EmbeddingResultLike:
        """Generate embeddings for a list of texts."""
        ...


# =============================================================================
# Result Dataclass
# =============================================================================


@dataclass
class ScoredJob:
    """Result of scoring a single job against a persona.

    REQ-008 §10.1: Batch scoring returns these for each job.

    Attributes:
        job_id: UUID of the job posting that was scored.
        fit_score: Fit Score result with total and component breakdown.
        stretch_score: Stretch Score result with total and component breakdown.
    """

    job_id: uuid.UUID
    fit_score: FitScoreResult
    stretch_score: StretchScoreResult


# =============================================================================
# Helper Functions
# =============================================================================


def _convert_persona_skills(skills: list[Any]) -> list[PersonaSkillInput]:
    """Convert persona skills to dict format for hard_skills_match."""
    return [
        PersonaSkillInput(
            skill_name=s.skill_name,
            skill_type=s.skill_type,
            proficiency=s.proficiency,
        )
        for s in skills
    ]


def _convert_job_skills(skills: list[Any]) -> list[JobSkillInput]:
    """Convert job extracted skills to dict format for hard_skills_match."""
    return [
        JobSkillInput(
            skill_name=s.skill_name,
            skill_type=s.skill_type,
            is_required=s.is_required,
            years_requested=getattr(s, "years_requested", None),
        )
        for s in skills
    ]


def _get_job_skill_names(skills: list[Any]) -> list[str]:
    """Extract skill names from job skills for stretch score."""
    return [s.skill_name for s in skills]


def _build_job_titles_text(job: JobPostingLike) -> str:
    """Build text for job title embedding."""
    if not job.job_title or not job.job_title.strip():
        return ""
    return job.job_title.strip()


# =============================================================================
# Main Batch Scoring Function
# =============================================================================


async def batch_score_jobs(
    jobs: list[JobPostingLike],
    persona: PersonaLike,
    persona_embeddings: PersonaEmbeddingsResult,
    embedding_provider: EmbeddingProviderLike,
) -> list[ScoredJob]:
    """Score multiple jobs efficiently against a persona.

    REQ-008 §10.1: Batch Scoring.

    Optimizations:
    1. Persona embeddings are passed in (loaded once, reused across calls)
    2. Job embeddings generated in batch (single API call for all jobs)
    3. Component scoring is sequential (CPU-bound, no async benefit)

    Args:
        jobs: List of job postings to score.
        persona: User's persona with skills, experience, and preferences.
        persona_embeddings: Pre-computed persona embeddings (avoids re-generation).
        embedding_provider: Embedding provider for generating job embeddings.

    Returns:
        List of ScoredJob results, one per input job, in the same order.

    Raises:
        ValueError: If persona_embeddings.persona_id doesn't match persona.id,
            or if batch size exceeds maximum (_MAX_BATCH_SIZE).
    """
    # Validate batch size (DoS protection)
    if len(jobs) > _MAX_BATCH_SIZE:
        msg = f"Batch size {len(jobs)} exceeds maximum of {_MAX_BATCH_SIZE}"
        raise ValueError(msg)

    # Validate persona embeddings match persona
    if persona_embeddings.persona_id != persona.id:
        msg = (
            f"persona_id mismatch: embeddings for {persona_embeddings.persona_id}, "
            f"persona is {persona.id}"
        )
        raise ValueError(msg)

    # Early return for empty jobs list
    if not jobs:
        return []

    # -------------------------------------------------------------------------
    # Step 1: Generate job embeddings in batch (optimization #2)
    # -------------------------------------------------------------------------
    # Collect texts for batch embedding
    job_titles_texts: list[str] = []
    job_culture_texts: list[str] = []

    for job in jobs:
        job_titles_texts.append(_build_job_titles_text(job))
        job_culture_texts.append(build_culture_text(job.culture_text))

    # Generate title embeddings for all jobs at once
    # Filter out empty texts and track indices
    non_empty_title_indices = [i for i, t in enumerate(job_titles_texts) if t]
    non_empty_titles = [job_titles_texts[i] for i in non_empty_title_indices]

    job_title_embeddings: list[list[float] | None] = [None] * len(jobs)
    if non_empty_titles:
        title_result = await embedding_provider.embed(non_empty_titles)
        # Validate response count matches request (defense-in-depth)
        if len(title_result.vectors) != len(non_empty_titles):
            msg = (
                f"Embedding response count mismatch: "
                f"got {len(title_result.vectors)}, expected {len(non_empty_titles)}"
            )
            raise ValueError(msg)
        for idx, embedding_idx in enumerate(non_empty_title_indices):
            job_title_embeddings[embedding_idx] = title_result.vectors[idx]

    # Generate culture embeddings for all jobs at once
    non_empty_culture_indices = [i for i, t in enumerate(job_culture_texts) if t]
    non_empty_cultures = [job_culture_texts[i] for i in non_empty_culture_indices]

    job_culture_embeddings: list[list[float]] = [get_neutral_embedding()] * len(jobs)
    if non_empty_cultures:
        culture_result = await embedding_provider.embed(non_empty_cultures)
        # Validate response count matches request (defense-in-depth)
        if len(culture_result.vectors) != len(non_empty_cultures):
            msg = (
                f"Embedding response count mismatch: "
                f"got {len(culture_result.vectors)}, expected {len(non_empty_cultures)}"
            )
            raise ValueError(msg)
        for idx, embedding_idx in enumerate(non_empty_culture_indices):
            job_culture_embeddings[embedding_idx] = culture_result.vectors[idx]

    # -------------------------------------------------------------------------
    # Step 2: Score each job (sequential, CPU-bound)
    # -------------------------------------------------------------------------
    # Pre-convert persona skills once
    persona_skills_dict = _convert_persona_skills(persona.skills)

    results: list[ScoredJob] = []
    for i, job in enumerate(jobs):
        # Convert job skills
        job_skills_dict = _convert_job_skills(job.extracted_skills)
        job_skill_names = _get_job_skill_names(job.extracted_skills)

        # ---------------------------------------------------------------------
        # Calculate Fit Score components
        # ---------------------------------------------------------------------
        # Hard skills (40%)
        hard_skills_score = calculate_hard_skills_score(
            persona_skills_dict,
            job_skills_dict,
        )

        # Soft skills (15%) - using embeddings
        soft_skills_score = calculate_soft_skills_score(
            persona_embeddings.soft_skills.vector,
            job_culture_embeddings[i],
        )

        # Experience level (25%)
        experience_score = calculate_experience_score(
            persona.years_experience,
            job.years_experience_min,
            job.years_experience_max,
        )

        # Role title (10%) - using embeddings
        # Build user titles embedding (simplified: just use persona embedding for now)
        # In production, this would use a pre-computed user titles embedding
        role_title_score = calculate_role_title_score(
            persona.current_role,
            None,  # work_history_titles - not available in this interface
            job.job_title,
            None,  # user_titles_embedding - would need pre-computation
            job_title_embeddings[i],
        )

        # Location/logistics (10%)
        logistics_score = calculate_logistics_score(
            persona.remote_preference,
            persona.commutable_cities,
            job.work_model,
            job.location,
        )

        # Aggregate Fit Score
        fit_result = calculate_fit_score(
            hard_skills=hard_skills_score,
            soft_skills=soft_skills_score,
            experience_level=experience_score,
            role_title=role_title_score,
            location_logistics=logistics_score,
        )

        # ---------------------------------------------------------------------
        # Calculate Stretch Score components
        # ---------------------------------------------------------------------
        # Target role alignment (50%)
        # Uses job title embedding for semantic matching
        target_role_score = calculate_target_role_alignment(
            persona.target_roles,
            job.job_title,
            None,  # target_roles_embedding - would need pre-computation
            job_title_embeddings[i],
        )

        # Target skills exposure (40%)
        target_skills_score = calculate_target_skills_exposure(
            persona.target_skills,
            job_skill_names,
        )

        # Growth trajectory (10%)
        growth_trajectory_score = calculate_growth_trajectory(
            persona.current_role,
            job.job_title,
        )

        # Aggregate Stretch Score
        stretch_result = calculate_stretch_score(
            target_role=target_role_score,
            target_skills=target_skills_score,
            growth_trajectory=growth_trajectory_score,
        )

        # ---------------------------------------------------------------------
        # Build result
        # ---------------------------------------------------------------------
        results.append(
            ScoredJob(
                job_id=job.id,
                fit_score=fit_result,
                stretch_score=stretch_result,
            )
        )

    return results
