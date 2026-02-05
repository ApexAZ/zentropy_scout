"""Base resume selection service for the Ghostwriter agent.

REQ-007 §8.3: Base Resume Selection — Match role_type to job title,
fall back to is_primary.

Algorithm:
1. Filter to active resumes only (status='Active')
2. For each resume, compare normalized role_type to normalized job title
3. If match found → use matched resume
4. Fallback → use is_primary=True resume
5. If no primary → raise error
"""

import logging
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from app.services.role_title_match import normalize_title

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definition
# =============================================================================


class BaseResumeLike(Protocol):
    """Protocol for base resume data needed for selection.

    Matches the fields needed from BaseResume for role_type matching.
    """

    @property
    def id(self) -> UUID:
        """Base resume ID."""
        ...

    @property
    def role_type(self) -> str:
        """Role type this resume is tailored for."""
        ...

    @property
    def is_primary(self) -> bool:
        """Whether this is the user's primary/default resume."""
        ...

    @property
    def status(self) -> str:
        """Resume status ('Active' or 'Archived')."""
        ...


# =============================================================================
# Result Type
# =============================================================================


@dataclass
class BaseResumeSelectionResult:
    """Result of base resume selection.

    Attributes:
        base_resume_id: UUID of the selected base resume.
        match_reason: How the resume was selected.
            "role_type_match" if role_type matched job title.
            "primary_fallback" if fell back to is_primary.
    """

    base_resume_id: UUID
    match_reason: Literal["role_type_match", "primary_fallback"]


# =============================================================================
# Matching Function
# =============================================================================


def role_type_matches(role_type: str, job_title: str) -> bool:
    """Check if a base resume's role_type matches a job title.

    REQ-007 §8.3: Uses title normalization from REQ-008 §4.5.2
    for consistent comparison (case, synonyms, seniority prefixes).

    Args:
        role_type: Base resume's role_type field.
        job_title: Job posting's title.

    Returns:
        True if normalized role_type equals normalized job title.
    """
    if not role_type or not role_type.strip():
        return False
    if not job_title or not job_title.strip():
        return False

    normalized_role = normalize_title(role_type)
    normalized_job = normalize_title(job_title)

    if not normalized_role or not normalized_job:
        return False

    return normalized_role == normalized_job


# =============================================================================
# Selection Function
# =============================================================================


def select_base_resume(
    base_resumes: list[BaseResumeLike],
    job_title: str,
) -> BaseResumeSelectionResult:
    """Select the best base resume for a job posting.

    REQ-007 §8.3: Match role_type to job title, fall back to is_primary.

    Algorithm:
    1. Filter to active resumes only
    2. Try role_type match (first match wins)
    3. Fall back to primary resume
    4. Error if no match and no primary

    Args:
        base_resumes: All base resumes for the persona (any status).
        job_title: Target job posting's title.

    Returns:
        BaseResumeSelectionResult with selected resume ID and reason.

    Raises:
        ValueError: If no active resumes exist, or no match and no primary.
    """
    # Filter to active resumes only
    active_resumes = [r for r in base_resumes if r.status == "Active"]

    if not active_resumes:
        raise ValueError("No active base resumes available for selection")

    # Step 1: Try role_type match
    for resume in active_resumes:
        if role_type_matches(resume.role_type, job_title):
            logger.info(
                "Selected base resume %s by role_type match (role=%s, job=%s)",
                resume.id,
                resume.role_type,
                job_title,
            )
            return BaseResumeSelectionResult(
                base_resume_id=resume.id,
                match_reason="role_type_match",
            )

    # Step 2: Fall back to primary
    for resume in active_resumes:
        if resume.is_primary:
            logger.info(
                "Selected base resume %s by primary fallback (job=%s)",
                resume.id,
                job_title,
            )
            return BaseResumeSelectionResult(
                base_resume_id=resume.id,
                match_reason="primary_fallback",
            )

    # Step 3: No match and no primary
    raise ValueError(
        "No primary base resume found. Please mark one base resume as primary."
    )
