"""Onboarding workflow — persist gathered data into database entities.

REQ-002 §6.1: After the onboarding agent finishes gathering data via
the interview flow, this service persists everything atomically:

1. Updates Persona contact fields from basic_info
2. Updates Persona preferences from non_negotiables and growth_targets
3. Creates Tier 2 content (WorkHistory, Bullets, Skills, Education,
   Certifications, AchievementStories, VoiceProfile)
4. Creates BaseResume entries from base_resume_setup
5. Sets persona.onboarding_complete = True
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidStateError, NotFoundError
from app.models.persona import Persona
from app.models.persona_content import (
    AchievementStory,
    Bullet,
    Certification,
    Education,
    Skill,
    WorkHistory,
)
from app.models.persona_settings import VoiceProfile
from app.models.resume import BaseResume

# WHY Any not used: gathered_data keys are accessed via .get() with defaults,
# and each helper explicitly extracts and validates the types it needs.
# The top-level dict is typed as dict[str, object] for safety.

_FALLBACK = "Unknown"
"""Default value for missing required string fields."""

_ENTRIES_KEY = "entries"
"""Key used for item lists inside each gathered_data section."""

_MAX_WORK_ENTRIES = 50
"""Safety bound on work history entries (defense-in-depth)."""

_MAX_SKILL_ENTRIES = 100
"""Safety bound on skill entries (defense-in-depth)."""

_MAX_EDUCATION_ENTRIES = 20
"""Safety bound on education entries (defense-in-depth)."""

_MAX_CERTIFICATION_ENTRIES = 50
"""Safety bound on certification entries (defense-in-depth)."""

_MAX_STORY_ENTRIES = 30
"""Safety bound on achievement story entries (defense-in-depth)."""

_MAX_RESUME_ENTRIES = 10
"""Safety bound on base resume entries (defense-in-depth)."""

_MAX_BULLETS_PER_JOB = 20
"""Safety bound on bullet points per work history entry."""

_SALARY_STRIP_RE = re.compile(r"[^\d]")
"""Regex to strip non-digit chars from salary strings like '$150,000'."""


@dataclass(frozen=True)
class OnboardingResult:
    """Summary of entities created during onboarding finalization."""

    work_history_count: int
    skill_count: int
    education_count: int
    certification_count: int
    story_count: int
    base_resume_count: int


# =============================================================================
# Parsing Helpers
# =============================================================================


def _parse_salary(raw: str) -> int | None:
    """Parse a salary string into an integer.

    Handles formats like '120000', '$150,000'.

    Args:
        raw: Raw salary string from user input.

    Returns:
        Integer salary or None if unparseable.
    """
    cleaned = _SALARY_STRIP_RE.sub("", raw)
    if not cleaned:
        return None
    return int(cleaned)


def _parse_location(raw: str) -> tuple[str, str]:
    """Parse a location string into (city, state).

    Args:
        raw: Location string like 'Austin, TX' or 'Remote'.

    Returns:
        Tuple of (city, state). State defaults to empty string if not present.
    """
    parts = [p.strip() for p in raw.split(",", maxsplit=1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], ""


def _parse_year_month(raw: str) -> date:
    """Parse a YYYY-MM string into a date (first of month).

    Args:
        raw: Date string like '2020-01'.

    Returns:
        date object set to the first of the month, or 2000-01-01 on parse error.
    """
    try:
        parts = raw.split("-")
        return date(int(parts[0]), int(parts[1]), 1)
    except (IndexError, ValueError):
        return date(2000, 1, 1)


def _parse_comma_list(raw: str) -> list[str]:
    """Parse a comma-separated string into a list of trimmed items.

    Args:
        raw: String like 'Python, SQL, Docker'.

    Returns:
        List of stripped, non-empty strings.
    """
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_visa(raw: str) -> bool:
    """Parse visa sponsorship response to boolean.

    Args:
        raw: String like 'yes', 'no', 'true', 'false'.

    Returns:
        True if sponsorship is required, False otherwise.
    """
    return raw.strip().lower() in ("yes", "true", "required")


def _safe_int(raw: object, default: int = 0) -> int:
    """Safely parse a value to int with fallback.

    Args:
        raw: Value to parse (string or number).
        default: Fallback if parsing fails.

    Returns:
        Parsed integer or default.
    """
    try:
        return int(str(raw).strip())
    except (ValueError, TypeError):
        return default


# =============================================================================
# Section Persistence Helpers
# =============================================================================


def _update_contact_fields(persona: Persona, gathered_data: dict[str, object]) -> None:
    """Update Persona contact fields from basic_info section."""
    basic_info = gathered_data.get("basic_info", {})
    if not isinstance(basic_info, dict):
        return
    if basic_info.get("full_name"):
        persona.full_name = str(basic_info["full_name"])
    if basic_info.get("email"):
        persona.email = str(basic_info["email"])
    if basic_info.get("phone"):
        persona.phone = str(basic_info["phone"])
    if basic_info.get("location"):
        city, state = _parse_location(str(basic_info["location"]))
        persona.home_city = city
        if state:
            persona.home_state = state


def _apply_non_negotiables(persona: Persona, non_neg: dict[str, object]) -> None:
    """Apply non-negotiable preferences to persona."""
    if non_neg.get("remote_preference"):
        persona.remote_preference = str(non_neg["remote_preference"])
    if non_neg.get("minimum_base_salary"):
        salary = _parse_salary(str(non_neg["minimum_base_salary"]))
        if salary is not None:
            persona.minimum_base_salary = salary
    if non_neg.get("visa_sponsorship"):
        persona.visa_sponsorship_required = _parse_visa(
            str(non_neg["visa_sponsorship"])
        )
    if non_neg.get("commutable_cities"):
        persona.commutable_cities = _parse_comma_list(str(non_neg["commutable_cities"]))
    if non_neg.get("industry_exclusions"):
        persona.industry_exclusions = _parse_comma_list(
            str(non_neg["industry_exclusions"])
        )


def _apply_growth_targets(persona: Persona, growth: dict[str, object]) -> None:
    """Apply growth target preferences to persona."""
    if growth.get("target_roles"):
        persona.target_roles = _parse_comma_list(str(growth["target_roles"]))
    if growth.get("target_skills"):
        persona.target_skills = _parse_comma_list(str(growth["target_skills"]))


def _update_preferences(persona: Persona, gathered_data: dict[str, object]) -> None:
    """Update Persona preferences from non_negotiables and growth_targets."""
    non_neg = gathered_data.get("non_negotiables", {})
    if isinstance(non_neg, dict):
        _apply_non_negotiables(persona, non_neg)

    growth = gathered_data.get("growth_targets", {})
    if isinstance(growth, dict):
        _apply_growth_targets(persona, growth)


async def _create_work_history(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
) -> list[str]:
    """Create WorkHistory + Bullet entries. Returns list of created job IDs."""
    work_data = gathered_data.get("work_history", {})
    if not isinstance(work_data, dict):
        return []
    entries = list(work_data.get(_ENTRIES_KEY, []))[:_MAX_WORK_ENTRIES]
    created_ids: list[str] = []

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        end_date_raw = entry.get("end_date")
        end_date = _parse_year_month(str(end_date_raw)) if end_date_raw else None
        job = WorkHistory(
            persona_id=persona_id,
            job_title=str(entry.get("job_title", _FALLBACK)),
            company_name=str(entry.get("company", _FALLBACK)),
            start_date=_parse_year_month(str(entry.get("start_date", "2000-01"))),
            end_date=end_date,
            is_current=end_date is None,
            location=str(entry.get("location", "Not specified")),
            work_model=str(entry.get("work_model", "Onsite")),
            display_order=i,
        )
        db.add(job)
        await db.flush()
        created_ids.append(str(job.id))

        bullets = list(entry.get("bullets", []))[:_MAX_BULLETS_PER_JOB]
        for j, bullet_text in enumerate(bullets):
            db.add(
                Bullet(
                    work_history_id=job.id,
                    text=str(bullet_text),
                    display_order=j,
                )
            )

    return created_ids


async def _create_skills(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
) -> list[str]:
    """Create Skill entries. Returns list of created skill IDs."""
    skills_data = gathered_data.get("skills", {})
    if not isinstance(skills_data, dict):
        return []
    entries = list(skills_data.get(_ENTRIES_KEY, []))[:_MAX_SKILL_ENTRIES]
    created_ids: list[str] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category = str(entry.get("category", "Hard"))
        skill_type = "Hard" if category.lower() in ("hard", "technical") else "Soft"
        skill = Skill(
            persona_id=persona_id,
            skill_name=str(entry.get("skill_name", _FALLBACK)),
            skill_type=skill_type,
            category=category,
            proficiency=str(entry.get("proficiency", "Familiar")),
            years_used=0,
            last_used="Current",
        )
        db.add(skill)
        await db.flush()
        created_ids.append(str(skill.id))

    return created_ids


def _create_education(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
) -> int:
    """Create Education entries if not skipped. Returns count."""
    edu_data = gathered_data.get("education", {})
    if not isinstance(edu_data, dict) or edu_data.get("skipped"):
        return 0
    entries = list(edu_data.get(_ENTRIES_KEY, []))[:_MAX_EDUCATION_ENTRIES]
    count = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        db.add(
            Education(
                persona_id=persona_id,
                degree=str(entry.get("degree", _FALLBACK)),
                institution=str(entry.get("institution", _FALLBACK)),
                field_of_study=str(entry.get("field_of_study", "General Studies")),
                graduation_year=_safe_int(entry.get("graduation_year", 2000), 2000),
                display_order=i,
            )
        )
        count += 1

    return count


def _create_certifications(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
) -> int:
    """Create Certification entries if not skipped. Returns count."""
    cert_data = gathered_data.get("certifications", {})
    if not isinstance(cert_data, dict) or cert_data.get("skipped"):
        return 0
    entries = list(cert_data.get(_ENTRIES_KEY, []))[:_MAX_CERTIFICATION_ENTRIES]
    count = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        db.add(
            Certification(
                persona_id=persona_id,
                certification_name=str(entry.get("name", _FALLBACK)),
                issuing_organization=str(entry.get("issuing_organization", _FALLBACK)),
                date_obtained=_parse_year_month(
                    str(entry.get("obtained_date", "2000-01"))
                ),
                display_order=i,
            )
        )
        count += 1

    return count


def _create_stories(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
) -> int:
    """Create AchievementStory entries. Returns count."""
    stories_data = gathered_data.get("achievement_stories", {})
    if not isinstance(stories_data, dict):
        return 0
    entries = list(stories_data.get(_ENTRIES_KEY, []))[:_MAX_STORY_ENTRIES]
    count = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        skills_text = str(entry.get("skills", ""))
        db.add(
            AchievementStory(
                persona_id=persona_id,
                title=f"Achievement {i + 1}",
                context=str(entry.get("situation", "")),
                action=str(entry.get("actions", "")),
                outcome=str(entry.get("outcome", "")),
                skills_demonstrated=_parse_comma_list(skills_text)
                if skills_text
                else [],
                display_order=i,
            )
        )
        count += 1

    return count


def _create_voice_profile(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
) -> None:
    """Create VoiceProfile if voice data was gathered."""
    voice_data = gathered_data.get("voice_profile", {})
    if not isinstance(voice_data, dict) or not voice_data.get("tone"):
        return
    db.add(
        VoiceProfile(
            persona_id=persona_id,
            tone=str(voice_data.get("tone", "")),
            sentence_style=str(voice_data.get("sentence_style", "")),
            vocabulary_level=str(voice_data.get("vocabulary", "")),
            things_to_avoid=_parse_comma_list(
                str(voice_data.get("things_to_avoid", ""))
            ),
        )
    )


def _create_base_resumes(
    db: AsyncSession,
    persona_id: uuid.UUID,
    gathered_data: dict[str, object],
    job_ids: list[str],
    skill_ids: list[str],
) -> int:
    """Create BaseResume entries from base_resume_setup. Returns count."""
    resume_data = gathered_data.get("base_resume_setup", {})
    if not isinstance(resume_data, dict):
        return 0
    entries = list(resume_data.get(_ENTRIES_KEY, []))[:_MAX_RESUME_ENTRIES]
    count = 0

    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        role_type = str(entry.get("role_type", "General"))
        db.add(
            BaseResume(
                persona_id=persona_id,
                name=f"{role_type} Resume",
                role_type=role_type,
                summary=f"Resume targeting {role_type} roles.",
                is_primary=bool(entry.get("is_primary", False)),
                display_order=i,
                included_jobs=job_ids,
                skills_emphasis=skill_ids,
            )
        )
        count += 1

    return count


# =============================================================================
# Main Entry Point
# =============================================================================


async def finalize_onboarding(
    gathered_data: dict[str, object],
    persona_id: uuid.UUID,
    db: AsyncSession,
) -> OnboardingResult:
    """Persist all gathered onboarding data into database entities.

    This is called after the onboarding agent completes its interview flow.
    Commits the transaction on success.

    Args:
        gathered_data: The gathered data dict from the onboarding flow.
        persona_id: The persona to populate.
        db: Database session.

    Returns:
        OnboardingResult with counts of created entities.

    Raises:
        NotFoundError: If persona does not exist.
        InvalidStateError: If onboarding is already complete.
    """
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    if persona is None:
        raise NotFoundError("Persona", str(persona_id))

    if persona.onboarding_complete:
        raise InvalidStateError("Onboarding is already complete for this persona.")

    _update_contact_fields(persona, gathered_data)
    _update_preferences(persona, gathered_data)

    job_ids = await _create_work_history(db, persona_id, gathered_data)
    skill_ids = await _create_skills(db, persona_id, gathered_data)
    edu_count = _create_education(db, persona_id, gathered_data)
    cert_count = _create_certifications(db, persona_id, gathered_data)
    story_count = _create_stories(db, persona_id, gathered_data)
    _create_voice_profile(db, persona_id, gathered_data)
    resume_count = _create_base_resumes(
        db, persona_id, gathered_data, job_ids, skill_ids
    )

    persona.onboarding_complete = True
    persona.onboarding_step = None

    await db.commit()

    return OnboardingResult(
        work_history_count=len(job_ids),
        skill_count=len(skill_ids),
        education_count=edu_count,
        certification_count=cert_count,
        story_count=story_count,
        base_resume_count=resume_count,
    )
