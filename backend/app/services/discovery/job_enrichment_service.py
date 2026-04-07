"""Job enrichment service for skill extraction and ghost detection.

REQ-016 §6.3: Enriches raw job postings with extracted skills, culture
signals, and ghost detection scores.

Coordinates with:
  - discovery/ghost_detection.py — calls calculate_ghost_score for freshness analysis

Called by: discovery/job_fetch_service.py and unit tests.
"""

import json
import logging
from typing import Any

from app.core.llm_sanitization import sanitize_llm_input
from app.providers.errors import ProviderError
from app.providers.llm.base import LLMMessage, LLMProvider, TaskType
from app.services.discovery.ghost_detection import calculate_ghost_score

logger = logging.getLogger(__name__)

# Max characters to send to LLM for skill extraction per REQ-007 §6.4.
_MAX_DESCRIPTION_LENGTH = 15000

_EXTRACTION_SYSTEM_PROMPT = """\
You are a job posting parser. Extract structured information from the job description.

Return a JSON object with exactly these fields:
- required_skills: list of strings — skills explicitly required in the posting
- preferred_skills: list of strings — skills listed as preferred, nice-to-have, or bonus
- culture_text: string or null — key cultural signals (values, work style, team environment); \
null if none present

Keep skill names concise and normalized (e.g. "Python", "Docker", "machine learning").
Return only the JSON object, no additional text."""


def _empty_extraction() -> dict[str, Any]:
    """Return the default empty extraction result."""
    return {
        "required_skills": [],
        "preferred_skills": [],
        "culture_text": None,
    }


def _coerce_string_list(value: Any) -> list[str]:
    """Coerce an LLM response value to a list of strings.

    LLMs occasionally return unexpected types (dicts, nulls, mixed lists).
    Silently drops non-string elements rather than raising.

    Args:
        value: Parsed JSON value that should be a list of strings.

    Returns:
        List containing only the string elements from value, or [] if
        value is not a list.
    """
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


async def _score_single_job(
    job: dict[str, Any],
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Calculate ghost score for a single job, returning enriched copy.

    Args:
        job: Raw job dict with optional scoring fields.
        provider: Optional LLM provider for ghost detection.

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
            provider=provider,
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


async def _enrich_single_job(
    job: dict[str, Any],
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Run extraction + ghost scoring for a single job.

    Errors in one step don't block the other.

    Args:
        job: Raw job dict to enrich.
        provider: Optional LLM provider for ghost detection.

    Returns:
        Enriched copy with extraction + ghost fields.
    """
    description = job.get("description", "")
    current = dict(job)

    # Step 1: Extract skills and culture
    try:
        extraction = await JobEnrichmentService.extract_skills_and_culture(
            description, provider
        )
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
            provider=provider,
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
        provider: LLMProvider | None = None,
    ) -> dict[str, Any]:
        """Extract skills and culture text from a job description.

        Truncates input to 15k chars, sanitizes via LLM input pipeline,
        then calls the LLM to extract required/preferred skills and culture
        signals. When no provider is given (test/stub mode), returns empty
        extraction without making an LLM call.

        Args:
            description: Job description text.
            provider: LLM provider for extraction. Pass None to skip the
                LLM call and return an empty extraction (test/stub mode).

        Returns:
            Dict with required_skills (list[str]), preferred_skills (list[str]),
            and culture_text (str or None). LLM errors are caught and logged;
            this method never raises.
        """
        if not description:
            return _empty_extraction()

        # Truncate BEFORE sanitize — injection patterns are stripped in-budget.
        # Do not swap: sanitization must see the same content the LLM will receive.
        truncated = description[:_MAX_DESCRIPTION_LENGTH]

        # Sanitize on read — all pool content through sanitize_llm_input()
        truncated = sanitize_llm_input(truncated)

        logger.debug(
            "Skill extraction called (description length: %d, truncated: %d)",
            len(description),
            len(truncated),
        )

        if provider is None:
            return _empty_extraction()

        try:
            response = await provider.complete(
                messages=[
                    LLMMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
                    LLMMessage(role="user", content=truncated),
                ],
                task=TaskType.EXTRACTION,
                json_mode=True,
            )
            data = json.loads(response.content or "{}")
            return {
                "required_skills": _coerce_string_list(data.get("required_skills")),
                "preferred_skills": _coerce_string_list(data.get("preferred_skills")),
                "culture_text": (
                    data.get("culture_text")
                    if isinstance(data.get("culture_text"), str)
                    else None
                ),
            }
        except (ProviderError, json.JSONDecodeError, TypeError, AttributeError) as e:
            logger.warning("Skill extraction LLM call failed: %s", e, exc_info=True)
            return _empty_extraction()

    @staticmethod
    async def calculate_ghost_scores(
        jobs: list[dict[str, Any]],
        provider: LLMProvider | None = None,
    ) -> list[dict[str, Any]]:
        """Calculate ghost detection scores for a batch of jobs.

        Delegates to ghost_detection.calculate_ghost_score() per job.
        Errors are recorded per-job but do not fail the batch.

        Args:
            jobs: List of job dicts to score.
            provider: Optional LLM provider for ghost detection.

        Returns:
            List of jobs enriched with ghost_score and ghost_signals.
        """
        return [await _score_single_job(job, provider=provider) for job in jobs]

    @staticmethod
    async def enrich_jobs(
        jobs: list[dict[str, Any]],
        provider: LLMProvider | None = None,
    ) -> list[dict[str, Any]]:
        """Full enrichment pipeline: extraction + ghost scoring.

        For each job:
        1. Extract skills and culture text (LLM call)
        2. Calculate ghost detection score

        Errors in one step don't block the other. Per-job error handling
        ensures partial failures don't fail the entire batch.

        Args:
            jobs: List of raw job dicts to enrich.
            provider: Optional LLM provider for ghost detection.

        Returns:
            List of enriched job dicts with extraction + ghost fields.
        """
        return [await _enrich_single_job(job, provider=provider) for job in jobs]
