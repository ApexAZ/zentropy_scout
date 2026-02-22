"""Content security service for shared pool poisoning defense.

REQ-015 §8.4: Validates job content on write, manages quarantine
lifecycle, and enforces manual submission rate limits.

Mitigations:
1. Validate on write — reject injection patterns via detect_injection_patterns()
2. Quarantine manual submissions — visible only to submitter until confirmed
3. Rate limit manual submissions — max 20/user/day
4. Timing side-channel — handled at endpoint level (background processing)
5. Sanitize on read — handled at LLM prompt construction sites
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_sanitization import detect_injection_patterns
from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.persona_job import PersonaJob

logger = logging.getLogger(__name__)

# Quarantine auto-release period (REQ-015 §8.4 mitigation 3)
_QUARANTINE_DAYS = 7

# Maximum manual submissions per user per day (REQ-015 §8.4 mitigation 4)
_MAX_MANUAL_SUBMISSIONS_PER_DAY = 20


# =============================================================================
# Validation result
# =============================================================================


@dataclass(frozen=True)
class ContentValidationResult:
    """Result of content validation.

    Attributes:
        is_valid: True if content passes all checks.
        reason: Human-readable reason for rejection (empty if valid).
        field: Name of the field that failed validation (empty if valid).
    """

    is_valid: bool
    reason: str = ""
    field: str = ""


# =============================================================================
# Write-time validation (REQ-015 §8.4 mitigation 2)
# =============================================================================


_INJECTION_REASON = "Injection pattern detected in"


def validate_job_content(
    description: str,
    culture_text: str | None = None,
    modifications: dict[str, Any] | None = None,
    raw_text: str | None = None,
) -> ContentValidationResult:
    """Validate job content for injection patterns before pool storage.

    Checks description, raw_text, culture_text, and any user-supplied
    modification values (including nested strings in list items) for
    prompt injection.

    Args:
        description: Job description text.
        culture_text: Optional culture text.
        modifications: Optional dict of user-supplied field overrides.
        raw_text: Optional raw job posting text (stored as archive).

    Returns:
        ContentValidationResult with is_valid and reason.
    """
    if detect_injection_patterns(description):
        return ContentValidationResult(
            is_valid=False,
            reason=f"{_INJECTION_REASON} job description",
            field="description",
        )

    if raw_text and detect_injection_patterns(raw_text):
        return ContentValidationResult(
            is_valid=False,
            reason=f"{_INJECTION_REASON} raw text",
            field="raw_text",
        )

    if culture_text and detect_injection_patterns(culture_text):
        return ContentValidationResult(
            is_valid=False,
            reason=f"{_INJECTION_REASON} culture text",
            field="culture_text",
        )

    if modifications:
        result = _check_modifications_for_injection(modifications)
        if result is not None:
            return result

    return ContentValidationResult(is_valid=True)


def _check_modifications_for_injection(
    modifications: dict[str, Any],
) -> ContentValidationResult | None:
    """Check modification values for injection patterns.

    Handles both flat string values and nested strings inside list items
    (e.g., extracted_skills[].skill_name).

    Args:
        modifications: Dict of user-supplied field overrides.

    Returns:
        ContentValidationResult if injection found, None if clean.
    """
    for key, value in modifications.items():
        if isinstance(value, str) and detect_injection_patterns(value):
            return ContentValidationResult(
                is_valid=False,
                reason=f"{_INJECTION_REASON} modification '{key}'",
                field=key,
            )
        if isinstance(value, list):
            for i, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                for sub_key, sub_val in item.items():
                    if isinstance(sub_val, str) and detect_injection_patterns(sub_val):
                        return ContentValidationResult(
                            is_valid=False,
                            reason=f"{_INJECTION_REASON} {key}[{i}].{sub_key}",
                            field=key,
                        )
    return None


# =============================================================================
# Quarantine lifecycle (REQ-015 §8.4 mitigation 3)
# =============================================================================


def build_quarantine_fields(
    discovery_method: str,
) -> dict[str, Any]:
    """Build quarantine fields for a new job posting.

    Manual submissions are quarantined for 7 days. Scouter and pool
    discoveries are not quarantined.

    Args:
        discovery_method: How the job was discovered ('manual', 'scouter', 'pool').

    Returns:
        Dict with is_quarantined, quarantined_at, quarantine_expires_at.
    """
    if discovery_method == "manual":
        now = datetime.now(UTC)
        return {
            "is_quarantined": True,
            "quarantined_at": now,
            "quarantine_expires_at": now + timedelta(days=_QUARANTINE_DAYS),
        }

    return {
        "is_quarantined": False,
        "quarantined_at": None,
        "quarantine_expires_at": None,
    }


async def release_expired_quarantines(db: AsyncSession) -> int:
    """Release quarantined jobs whose expiry has passed.

    REQ-015 §8.4: 7-day auto-release. Jobs with quarantine_expires_at
    set to NULL (reported/flagged) are never auto-released.

    Args:
        db: Async database session (caller manages transaction).

    Returns:
        Number of quarantines released.
    """
    now = datetime.now(UTC)
    stmt = (
        update(JobPosting)
        .where(
            JobPosting.is_quarantined.is_(True),
            JobPosting.quarantine_expires_at.isnot(None),
            JobPosting.quarantine_expires_at <= now,
        )
        .values(is_quarantined=False)
    )
    result = await db.execute(stmt)
    released: int = result.rowcount  # type: ignore[attr-defined]  # CursorResult from UPDATE
    if released > 0:
        logger.info("Released %d expired quarantines", released)
    return released


async def lift_quarantine(db: AsyncSession, job_posting_id: uuid.UUID) -> None:
    """Lift quarantine on a job posting (independent confirmation).

    REQ-015 §8.4: When another user's Scouter finds the same job
    via API fetch, the quarantine is lifted.

    Args:
        db: Async database session.
        job_posting_id: UUID of the quarantined job posting.
    """
    job = await db.get(JobPosting, job_posting_id)
    if job is not None and job.is_quarantined:
        job.is_quarantined = False
        await db.flush()
        logger.info(
            "Lifted quarantine on job %s (independent confirmation)", job_posting_id
        )


# =============================================================================
# Rate limiting (REQ-015 §8.4 mitigation 4)
# =============================================================================


async def check_manual_submission_rate(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    """Check if user is under the manual submission rate limit.

    REQ-015 §8.4: Max 20 manual submissions per user per day.

    Args:
        db: Async database session.
        user_id: UUID of the authenticated user.

    Returns:
        True if submission is allowed, False if rate limited.
    """
    since = datetime.now(UTC) - timedelta(days=1)
    stmt = (
        select(func.count())
        .select_from(PersonaJob)
        .join(Persona, PersonaJob.persona_id == Persona.id)
        .where(
            Persona.user_id == user_id,
            PersonaJob.discovery_method == "manual",
            PersonaJob.discovered_at >= since,
        )
    )
    result = await db.execute(stmt)
    count = result.scalar_one()
    return count < _MAX_MANUAL_SUBMISSIONS_PER_DAY
