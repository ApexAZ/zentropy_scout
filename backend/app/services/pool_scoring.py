"""Lightweight scoring functions for pool surfacing.

REQ-015 §7.2, REQ-008 §4: Pure scoring functions for keyword pre-screen,
experience alignment, work model alignment, seniority alignment, and
keyword overlap. No database access, no side effects.

Used by pool_surfacing_service.py for background job-persona matching
without LLM calls.
"""

from app.models.job_posting import JobPosting
from app.models.persona import Persona
from app.models.persona_content import Skill
from app.services.fit_score import (
    FIT_NEUTRAL_SCORE,
    FitScoreResult,
    calculate_fit_score,
)

# Work model alignment matrix.
# Maps (persona_preference, job_work_model) to a score 0-100.
# 'No Preference' always scores 100.
_WORK_MODEL_SCORES: dict[tuple[str, str], float] = {
    ("Remote Only", "Remote"): 100.0,
    ("Remote Only", "Hybrid"): 30.0,
    ("Remote Only", "Onsite"): 0.0,
    ("Hybrid OK", "Remote"): 90.0,
    ("Hybrid OK", "Hybrid"): 100.0,
    ("Hybrid OK", "Onsite"): 40.0,
    ("Onsite OK", "Remote"): 80.0,
    ("Onsite OK", "Hybrid"): 90.0,
    ("Onsite OK", "Onsite"): 100.0,
}

# Seniority ordering for distance calculation.
_SENIORITY_ORDER: dict[str, int] = {
    "Entry": 0,
    "Mid": 1,
    "Senior": 2,
    "Lead": 3,
    "Executive": 4,
}

# Map persona years_experience to approximate seniority level.
_YEARS_TO_SENIORITY: list[tuple[int, str]] = [
    (0, "Entry"),
    (3, "Mid"),
    (6, "Senior"),
    (11, "Lead"),
    (16, "Executive"),
]


# ---------------------------------------------------------------------------
# Pure scoring functions (no DB, no side effects)
# ---------------------------------------------------------------------------


def keyword_pre_screen(
    job_title: str,
    job_description: str,
    persona_skill_names: list[str],
) -> bool:
    """Check if any persona skill appears in the job text.

    REQ-015 §7.4: Lightweight pre-screen before full scoring.
    Case-insensitive substring matching.

    Args:
        job_title: Job title text.
        job_description: Job description text.
        persona_skill_names: List of skill names from the persona.

    Returns:
        True if at least one skill name appears in the job text.
    """
    if not persona_skill_names:
        return False

    job_text = f"{job_title} {job_description}".lower()
    return any(skill.lower() in job_text for skill in persona_skill_names)


def score_experience_alignment(
    persona_years: int | None,
    job_years_min: int | None,
    job_years_max: int | None,
) -> float:
    """Score how well persona experience matches job requirements.

    REQ-008 §4.4: Experience Level component.

    Scoring:
    - Within range: 100
    - Below min: penalty proportional to gap (20 pts per year short)
    - Above max: small penalty (5 pts per year over — overqualification)
    - Missing data: neutral score (70)

    Args:
        persona_years: Persona's years of experience (None = unknown).
        job_years_min: Job's minimum years required (None = any).
        job_years_max: Job's maximum years required (None = any).

    Returns:
        Score 0-100.
    """
    if persona_years is None:
        return FIT_NEUTRAL_SCORE
    if job_years_min is None and job_years_max is None:
        return FIT_NEUTRAL_SCORE

    if job_years_min is not None and persona_years < job_years_min:
        gap = job_years_min - persona_years
        return max(0.0, 100.0 - gap * 20.0)

    if job_years_max is not None and persona_years > job_years_max:
        gap = persona_years - job_years_max
        return max(0.0, 100.0 - gap * 5.0)

    return 100.0


def score_work_model_alignment(
    persona_preference: str | None,
    job_work_model: str | None,
) -> float:
    """Score work model alignment between persona and job.

    REQ-008 §4.6: Location/Logistics component.

    Args:
        persona_preference: Persona's remote_preference value.
        job_work_model: Job's work_model value.

    Returns:
        Score 0-100.
    """
    if persona_preference is None or persona_preference == "No Preference":
        return 100.0
    if job_work_model is None:
        return FIT_NEUTRAL_SCORE

    return _WORK_MODEL_SCORES.get(
        (persona_preference, job_work_model), FIT_NEUTRAL_SCORE
    )


def score_seniority_alignment(
    persona_years: int | None,
    job_seniority: str | None,
) -> float:
    """Score seniority level alignment.

    Maps persona years to an approximate seniority level, then compares
    with the job's seniority. Each level of distance penalizes by 25 pts.

    Args:
        persona_years: Persona's years of experience.
        job_seniority: Job's seniority level (Entry/Mid/Senior/Lead/Executive).

    Returns:
        Score 0-100.
    """
    if persona_years is None or job_seniority is None:
        return FIT_NEUTRAL_SCORE

    if job_seniority not in _SENIORITY_ORDER:
        return FIT_NEUTRAL_SCORE

    persona_seniority = _years_to_seniority(persona_years)
    persona_level = _SENIORITY_ORDER[persona_seniority]
    job_level = _SENIORITY_ORDER[job_seniority]

    distance = abs(persona_level - job_level)
    return max(0.0, 100.0 - distance * 25.0)


def _years_to_seniority(years: int) -> str:
    """Map years of experience to approximate seniority level."""
    result = "Entry"
    for threshold, level in _YEARS_TO_SENIORITY:
        if years >= threshold:
            result = level
    return result


def score_keyword_overlap(
    job_title: str,
    job_description: str,
    persona_skill_names: list[str],
) -> float:
    """Score hard skills match via keyword overlap.

    REQ-008 §4.2 lightweight approximation. Counts how many persona
    skills appear in the job text as a proportion of total persona skills.

    Args:
        job_title: Job title text.
        job_description: Job description text.
        persona_skill_names: List of skill names from the persona.

    Returns:
        Score 0-100.
    """
    if not persona_skill_names:
        return FIT_NEUTRAL_SCORE

    job_text = f"{job_title} {job_description}".lower()
    matches = sum(1 for skill in persona_skill_names if skill.lower() in job_text)
    proportion = matches / len(persona_skill_names)

    # Scale: 30%+ overlap → 100, linear below that
    if proportion >= 0.3:
        return 100.0
    return round(proportion / 0.3 * 100.0, 1)


def calculate_lightweight_fit(
    job: JobPosting,
    persona: Persona,
    persona_skills: list[Skill],
) -> FitScoreResult:
    """Calculate a lightweight fit score without LLM calls.

    Uses keyword overlap for hard skills, neutral scores for soft skills
    and role title (require embeddings/LLM), and direct comparison for
    experience and work model.

    Args:
        job: The job posting to score.
        persona: The persona to score against.
        persona_skills: Loaded skill objects for the persona.

    Returns:
        FitScoreResult with total score and component breakdown.
    """
    hard_skill_names = [s.skill_name for s in persona_skills if s.skill_type == "Hard"]

    hard_skills = score_keyword_overlap(
        job.job_title, job.description or "", hard_skill_names
    )
    experience_level = score_experience_alignment(
        persona.years_experience,
        job.years_experience_min,
        job.years_experience_max,
    )
    location_logistics = score_work_model_alignment(
        persona.remote_preference,
        job.work_model,
    )

    return calculate_fit_score(
        hard_skills=hard_skills,
        soft_skills=FIT_NEUTRAL_SCORE,
        experience_level=experience_level,
        role_title=FIT_NEUTRAL_SCORE,
        location_logistics=location_logistics,
    )
