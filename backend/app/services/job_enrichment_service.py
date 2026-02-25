"""Job enrichment service for skill extraction and ghost detection.

REQ-016 §6.3: Enriches raw job postings with extracted skills, culture
signals, and ghost detection scores. Extracts enrichment logic from
scouter_graph.py into a standalone async service.
"""

import logging
from typing import Any

from app.core.llm_sanitization import sanitize_llm_input
from app.services.ghost_detection import calculate_ghost_score

logger = logging.getLogger(__name__)

# Max characters to send to LLM for skill extraction per REQ-007 §6.4.
_MAX_DESCRIPTION_LENGTH = 15000


def _empty_extraction() -> dict[str, Any]:
    """Return the default empty extraction result."""
    return {
        "required_skills": [],
        "preferred_skills": [],
        "culture_text": None,
    }


async def _score_single_job(job: dict[str, Any]) -> dict[str, Any]:
    """Calculate ghost score for a single job, returning enriched copy.

    Args:
        job: Raw job dict with optional scoring fields.

    Returns:
        Copy of job with ghost_score and ghost_signals added.
    """
    try:
        signals = await calculate_ghost_score(
            posted_date=None,
            first_seen_date=None,
            repost_count=0,
            salary_min=job.get("salary_min"),
            salary_max=job.get("salary_max"),
            application_deadline=job.get("application_deadline"),
            location=job.get("location"),
            seniority_level=job.get("seniority_level"),
            years_experience_min=job.get("years_experience_min"),
            description=job.get("description", ""),
        )
        return {
            **job,
            "ghost_score": signals.ghost_score,
            "ghost_signals": signals.to_dict(),
        }
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Ghost score calculation failed for job %s: %s",
            job.get("external_id"),
            e,
        )
        return {
            **job,
            "ghost_score": None,
            "ghost_signals": None,
        }


async def _enrich_single_job(job: dict[str, Any]) -> dict[str, Any]:
    """Run extraction + ghost scoring for a single job.

    Errors in one step don't block the other.

    Args:
        job: Raw job dict to enrich.

    Returns:
        Enriched copy with extraction + ghost fields.
    """
    description = job.get("description", "")
    current = dict(job)

    # Step 1: Extract skills and culture
    try:
        extraction = await JobEnrichmentService.extract_skills_and_culture(description)
        current["required_skills"] = extraction.get("required_skills", [])
        current["preferred_skills"] = extraction.get("preferred_skills", [])
        current["culture_text"] = extraction.get("culture_text")
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Skill extraction failed for job %s: %s",
            job.get("external_id"),
            e,
        )
        current.update(_empty_extraction())
        current["extraction_failed"] = True

    # Step 2: Ghost score
    try:
        signals = await calculate_ghost_score(
            posted_date=None,
            first_seen_date=None,
            repost_count=0,
            salary_min=job.get("salary_min"),
            salary_max=job.get("salary_max"),
            application_deadline=job.get("application_deadline"),
            location=job.get("location"),
            seniority_level=job.get("seniority_level"),
            years_experience_min=job.get("years_experience_min"),
            description=description,
        )
        current["ghost_score"] = signals.ghost_score
        current["ghost_signals"] = signals.to_dict()
    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Ghost score failed for job %s: %s",
            job.get("external_id"),
            e,
        )
        current["ghost_score"] = None
        current["ghost_signals"] = None

    return current


class JobEnrichmentService:
    """Enriches raw job postings with extracted skills and ghost detection.

    All methods are static — no instance state. The service is a pure
    function boundary: input jobs, output enriched jobs.
    """

    @staticmethod
    async def extract_skills_and_culture(
        description: str,
    ) -> dict[str, Any]:
        """Extract skills and culture text from a job description.

        Truncates input to 15k chars, sanitizes via LLM input pipeline,
        then extracts required/preferred skills and culture signals.

        Args:
            description: Job description text.

        Returns:
            Dict with required_skills, preferred_skills, and culture_text.

        Note:
            Currently returns placeholder extraction. Full LLM-based
            extraction will be implemented when the provider abstraction
            layer call is wired (uses get_provider() from app/providers/).
        """
        if not description:
            return _empty_extraction()

        # Truncate to 15k chars per REQ-007 §6.4
        truncated = description[:_MAX_DESCRIPTION_LENGTH]

        # Sanitize on read — all pool content through sanitize_llm_input()
        truncated = sanitize_llm_input(truncated)

        logger.debug(
            "Skill extraction called (description length: %d, truncated: %d)",
            len(description),
            len(truncated),
        )

        # Placeholder: returns empty extraction to allow pipeline testing.
        # Full LLM extraction will use get_provider() from app/providers/.
        return _empty_extraction()

    @staticmethod
    async def calculate_ghost_scores(
        jobs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Calculate ghost detection scores for a batch of jobs.

        Delegates to ghost_detection.calculate_ghost_score() per job.
        Errors are recorded per-job but do not fail the batch.

        Args:
            jobs: List of job dicts to score.

        Returns:
            List of jobs enriched with ghost_score and ghost_signals.
        """
        return [await _score_single_job(job) for job in jobs]

    @staticmethod
    async def enrich_jobs(
        jobs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Full enrichment pipeline: extraction + ghost scoring.

        For each job:
        1. Extract skills and culture text (LLM call)
        2. Calculate ghost detection score

        Errors in one step don't block the other. Per-job error handling
        ensures partial failures don't fail the entire batch.

        Args:
            jobs: List of raw job dicts to enrich.

        Returns:
            List of enriched job dicts with extraction + ghost fields.
        """
        return [await _enrich_single_job(job) for job in jobs]
