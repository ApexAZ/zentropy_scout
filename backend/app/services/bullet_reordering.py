"""Bullet reordering logic for resume tailoring.

REQ-010 §4.3: Bullet Reordering Logic.

Reorders resume bullets within each job entry to surface the most relevant
accomplishments first. Bullets are NEVER rewritten — only their display order
changes.

Relevance is scored 0.0–1.0 using four weighted factors:
- Skill overlap (40%): How many job-required skills appear in the bullet.
- Keyword presence (30%): How many job description keywords appear in the bullet.
- Quantified outcome bonus (20%): Flat bonus if the bullet contains metrics.
- Recency boost (10%): Bonus for current (0.1) or recent (0.05) job entries.

Pattern follows tailoring_decision.py: pure functions with pre-extracted data.
The caller (Ghostwriter agent) extracts skills/keywords/metrics before calling
these functions, keeping this module free of LLM and DB dependencies.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

_MAX_JOB_ENTRIES: int = 50
"""Maximum number of job entries allowed in a single reorder call."""

_MAX_BULLETS_PER_JOB: int = 100
"""Maximum number of bullets per job entry."""

_MAX_SKILLS: int = 1000
"""Maximum number of job skills allowed."""

_MAX_KEYWORDS: int = 1000
"""Maximum number of job keywords allowed."""

_SKILL_OVERLAP_WEIGHT: float = 0.4
"""Weight for skill overlap factor in relevance scoring."""

_KEYWORD_OVERLAP_WEIGHT: float = 0.3
"""Weight for keyword presence factor in relevance scoring."""

_METRICS_BONUS: float = 0.2
"""Flat bonus for bullets containing quantified outcomes."""

_RECENCY_CURRENT_BOOST: float = 0.1
"""Boost for bullets from the applicant's current job."""

_RECENCY_RECENT_BOOST: float = 0.05
"""Boost for bullets from jobs ended within 24 months."""


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class BulletData:
    """Pre-extracted data for a single resume bullet.

    All fields are pre-computed by the caller — this dataclass is a pure data
    container with no extraction logic.

    Attributes:
        bullet_id: Unique identifier for the bullet.
        job_entry_id: The work history entry this bullet belongs to.
        skills: Set of lowercased skill names extracted from the bullet text.
        keywords: Set of lowercased keywords extracted from the bullet text.
        has_metrics: Whether the bullet contains quantified outcomes.
        is_current_job: Whether this bullet is from the applicant's current job.
        is_recent_job: Whether the job ended within 24 months.
    """

    bullet_id: str
    job_entry_id: str
    skills: set[str]
    keywords: set[str]
    has_metrics: bool
    is_current_job: bool
    is_recent_job: bool


# =============================================================================
# Scoring
# =============================================================================


def calculate_bullet_relevance(
    *,
    bullet: BulletData,
    job_skills: set[str],
    job_keywords: set[str],
) -> float:
    """Score a bullet's relevance to a job posting.

    REQ-010 §4.3: Four weighted factors combine additively, capped at 1.0.

    Args:
        bullet: Pre-extracted bullet data.
        job_skills: Lowercased skill names from the job posting.
        job_keywords: Lowercased keywords from the job description.

    Returns:
        Relevance score between 0.0 and 1.0 (inclusive).
    """
    score = 0.0

    # Factor 1: Skill overlap (40%)
    if job_skills:
        overlap = len(bullet.skills & job_skills)
        score += (overlap / len(job_skills)) * _SKILL_OVERLAP_WEIGHT

    # Factor 2: Keyword presence (30%)
    if job_keywords:
        overlap = len(bullet.keywords & job_keywords)
        score += (overlap / len(job_keywords)) * _KEYWORD_OVERLAP_WEIGHT

    # Factor 3: Quantified outcome bonus (20%)
    if bullet.has_metrics:
        score += _METRICS_BONUS

    # Factor 4: Recency boost (10%)
    if bullet.is_current_job:
        score += _RECENCY_CURRENT_BOOST
    elif bullet.is_recent_job:
        score += _RECENCY_RECENT_BOOST

    return min(score, 1.0)


# =============================================================================
# Reordering
# =============================================================================


def reorder_bullets_for_job(
    *,
    bullets_by_job: dict[str, list[BulletData]],
    job_skills: set[str],
    job_keywords: set[str],
) -> dict[str, list[str]]:
    """Reorder bullets within each job entry by relevance to a job posting.

    REQ-010 §4.3: The most relevant accomplishment should be position 1 since
    many recruiters only read the first bullet. Content is never changed — only
    display order.

    Uses Python's stable sort to preserve relative order for bullets with equal
    relevance scores.

    Args:
        bullets_by_job: Dict mapping job_entry_id to list of BulletData for
            that entry. The list order represents the current display order.
        job_skills: Lowercased skill names from the job posting.
        job_keywords: Lowercased keywords from the job description.

    Returns:
        Dict mapping job_entry_id to ordered list of bullet_ids, with the
        most relevant bullet first.

    Raises:
        ValueError: If input sizes exceed safety bounds.
    """
    if len(bullets_by_job) > _MAX_JOB_ENTRIES:
        raise ValueError(
            f"bullets_by_job has {len(bullets_by_job)} entries, "
            f"exceeds maximum of {_MAX_JOB_ENTRIES}"
        )
    if len(job_skills) > _MAX_SKILLS:
        raise ValueError(
            f"job_skills has {len(job_skills)} items, exceeds maximum of {_MAX_SKILLS}"
        )
    if len(job_keywords) > _MAX_KEYWORDS:
        raise ValueError(
            f"job_keywords has {len(job_keywords)} items, "
            f"exceeds maximum of {_MAX_KEYWORDS}"
        )

    result: dict[str, list[str]] = {}

    for job_entry_id, bullets in bullets_by_job.items():
        if len(bullets) > _MAX_BULLETS_PER_JOB:
            raise ValueError(
                f"Job entry '{job_entry_id}' has {len(bullets)} bullets, "
                f"exceeds maximum of {_MAX_BULLETS_PER_JOB}"
            )
        scored = [
            (
                bullet.bullet_id,
                calculate_bullet_relevance(
                    bullet=bullet,
                    job_skills=job_skills,
                    job_keywords=job_keywords,
                ),
            )
            for bullet in bullets
        ]

        # Sort descending by score; stable sort preserves order for ties
        scored.sort(key=lambda x: -x[1])

        result[job_entry_id] = [bullet_id for bullet_id, _ in scored]

    logger.debug("Reordered bullets for %d job entries", len(result))
    return result
