"""Explanation Generation Logic.

REQ-008 §8.2: Explanation Generation Logic.

This module generates human-readable explanations for job-persona match scores.
It analyzes component scores and job/persona attributes to produce actionable
insights about strengths, gaps, stretch opportunities, and warnings.

The generate_explanation function is called by the Strategist agent (REQ-007 §7.6)
after scoring is complete.
"""

from typing import Any, Protocol

from app.services.fit_score import FitScoreResult
from app.services.hard_skills_match import normalize_skill
from app.services.score_explanation import ScoreExplanation
from app.services.stretch_score import StretchScoreResult

# =============================================================================
# Input Size Limits (defense in depth)
# =============================================================================

# Maximum number of skills to process (prevents resource exhaustion)
# Matches limits in hard_skills_match.py and stretch_score.py
_MAX_SKILLS = 500


# =============================================================================
# Thresholds (REQ-008 §8.2)
# =============================================================================

# Hard skills thresholds
_HARD_SKILLS_STRENGTH_THRESHOLD = 80  # >= 80 adds strength
_HARD_SKILLS_GAP_THRESHOLD = 50  # < 50 adds gap

# Experience thresholds
_EXPERIENCE_STRENGTH_THRESHOLD = 90  # >= 90 adds strength
_EXPERIENCE_GAP_THRESHOLD = 60  # < 60 adds gap or warning

# Stretch thresholds
_TARGET_SKILLS_STRETCH_THRESHOLD = 75  # >= 75 adds stretch opportunity
_TARGET_ROLE_STRETCH_THRESHOLD = 80  # >= 80 adds stretch opportunity

# Warning thresholds
_GHOST_SCORE_WARNING_THRESHOLD = 60  # >= 60 adds warning


# =============================================================================
# Protocol Definitions (for duck typing)
# =============================================================================


class PersonaLike(Protocol):
    """Protocol for objects with persona-like attributes."""

    years_experience: int | None
    current_role: str | None
    target_roles: list[Any]
    target_skills: list[Any]
    skills: list[Any]


class SkillLike(Protocol):
    """Protocol for objects with skill-like attributes."""

    skill_name: str
    skill_type: str


class ExtractedSkillLike(Protocol):
    """Protocol for objects with extracted skill-like attributes."""

    skill_name: str
    skill_type: str
    is_required: bool


class JobPostingLike(Protocol):
    """Protocol for objects with job posting-like attributes."""

    job_title: str
    years_experience_min: int | None
    years_experience_max: int | None
    salary_max: int | None
    ghost_score: int
    extracted_skills: list[Any]


# =============================================================================
# Helper Functions (REQ-008 §8.2)
# =============================================================================


def get_matched_skills(
    persona: PersonaLike,
    job: JobPostingLike,
    skill_type: str,
) -> list[str]:
    """Get skills that match between persona and job requirements.

    REQ-008 §8.2: Helper function for strength explanation.

    Compares persona skills against job's extracted skills of the same type,
    using normalized skill names for comparison.

    Args:
        persona: User's persona with skills attribute.
        job: Job posting with extracted_skills attribute.
        skill_type: Skill type to filter ("Hard" or "Soft").

    Returns:
        List of skill names that appear in both persona and job requirements.
    """
    # Build set of normalized job skill names for the requested type
    job_skill_names: set[str] = set()
    for skill in job.extracted_skills:
        if skill.skill_type == skill_type:
            job_skill_names.add(normalize_skill(skill.skill_name))

    # Find matching persona skills
    matched: list[str] = []
    for skill in persona.skills:
        if (
            skill.skill_type == skill_type
            and normalize_skill(skill.skill_name) in job_skill_names
        ):
            matched.append(skill.skill_name)

    return matched


def get_missing_skills(
    persona: PersonaLike,
    job: JobPostingLike,
    skill_type: str,
    required_only: bool = True,
) -> list[str]:
    """Get skills required by job that persona lacks.

    REQ-008 §8.2: Helper function for gap explanation.

    Identifies job skills that the persona doesn't have.

    Args:
        persona: User's persona with skills attribute.
        job: Job posting with extracted_skills attribute.
        skill_type: Skill type to filter ("Hard" or "Soft").
        required_only: If True, only return skills marked as required.

    Returns:
        List of skill names from job that persona is missing.
    """
    # Build set of normalized persona skill names for the requested type
    persona_skill_names: set[str] = set()
    for skill in persona.skills:
        if skill.skill_type == skill_type:
            persona_skill_names.add(normalize_skill(skill.skill_name))

    # Find job skills not in persona
    missing: list[str] = []
    for skill in job.extracted_skills:
        if skill.skill_type == skill_type:
            # Filter by required_only if specified
            if required_only and not skill.is_required:
                continue
            if normalize_skill(skill.skill_name) not in persona_skill_names:
                missing.append(skill.skill_name)

    return missing


def get_target_skill_matches(
    persona: PersonaLike,
    job: JobPostingLike,
) -> list[str]:
    """Get target skills that appear in job requirements.

    REQ-008 §8.2: Helper function for stretch opportunity explanation.

    Identifies persona's target skills that the job would expose them to.

    Args:
        persona: User's persona with target_skills attribute.
        job: Job posting with extracted_skills attribute.

    Returns:
        List of target skill names that appear in job requirements.
    """
    # Build set of normalized job skill names (any type)
    job_skill_names: set[str] = set()
    for skill in job.extracted_skills:
        job_skill_names.add(normalize_skill(skill.skill_name))

    # Find target skills that match
    matches: list[str] = []
    for target in persona.target_skills:
        if normalize_skill(target) in job_skill_names:
            matches.append(target)

    return matches


def generate_summary_sentence(
    fit_total: int,
    stretch_total: int,  # noqa: ARG001 - Reserved for future enhanced summaries
    strengths: list[str],
    gaps: list[str],
) -> str:
    """Generate a 2-3 sentence summary of the match quality.

    REQ-008 §8.2: Helper function for summary generation.

    Creates a human-readable overview based on overall scores and findings.

    Args:
        fit_total: Overall Fit Score (0-100).
        stretch_total: Overall Stretch Score (0-100). Reserved for future use.
        strengths: List of strength statements.
        gaps: List of gap statements.

    Returns:
        Summary sentence describing the match quality.
    """
    # Determine fit quality descriptor
    if fit_total >= 85:
        fit_quality = "strong fit"
    elif fit_total >= 70:
        fit_quality = "good fit"
    elif fit_total >= 55:
        fit_quality = "moderate fit"
    else:
        fit_quality = "weak fit"

    # Build summary based on strengths and gaps
    if strengths and not gaps:
        return (
            f"This role is a {fit_quality} for your background. "
            f"You meet the key requirements well."
        )
    elif strengths and gaps:
        return (
            f"This role is a {fit_quality} for your background. "
            f"You meet most requirements but may need to address some gaps."
        )
    elif not strengths and gaps:
        return (
            f"This role shows a {fit_quality}. "
            f"There are notable gaps between your background and the requirements."
        )
    else:
        # No strengths or gaps identified
        return f"This role shows a {fit_quality} for your background."


# =============================================================================
# Main Generation Function (REQ-008 §8.2)
# =============================================================================


def generate_explanation(
    fit_result: FitScoreResult,
    stretch_result: StretchScoreResult,
    persona: PersonaLike,
    job: JobPostingLike,
) -> ScoreExplanation:
    """Generate human-readable explanation of job-persona match scores.

    REQ-008 §8.2: Explanation Generation Logic.

    Analyzes component scores and job/persona attributes to produce
    actionable insights including strengths, gaps, stretch opportunities,
    and warnings.

    Args:
        fit_result: Result from calculate_fit_score with component breakdowns.
        stretch_result: Result from calculate_stretch_score with component breakdowns.
        persona: User's persona with skills, experience, and targets.
        job: Job posting with requirements, salary, and ghost score.

    Returns:
        ScoreExplanation with populated fields based on analysis.

    Raises:
        ValueError: If input skill lists exceed maximum size (_MAX_SKILLS).
    """
    # Validate input sizes (defense in depth)
    if len(persona.skills) > _MAX_SKILLS:
        msg = f"Persona skills exceed maximum of {_MAX_SKILLS}"
        raise ValueError(msg)
    if len(job.extracted_skills) > _MAX_SKILLS:
        msg = f"Job extracted skills exceed maximum of {_MAX_SKILLS}"
        raise ValueError(msg)
    if len(persona.target_skills) > _MAX_SKILLS:
        msg = f"Persona target skills exceed maximum of {_MAX_SKILLS}"
        raise ValueError(msg)

    strengths: list[str] = []
    gaps: list[str] = []
    stretch_opportunities: list[str] = []
    warnings: list[str] = []

    # -------------------------------------------------------------------------
    # Hard Skills Analysis (REQ-008 §8.2)
    # -------------------------------------------------------------------------
    hard_skills_score = fit_result.components.get("hard_skills", 70.0)

    if hard_skills_score >= _HARD_SKILLS_STRENGTH_THRESHOLD:
        matched = get_matched_skills(persona, job, "Hard")
        if matched:
            # Show up to 3 skills in the message
            skill_list = ", ".join(matched[:3])
            strengths.append(
                f"Strong technical fit — you have {len(matched)} of the key skills: {skill_list}"
            )
        else:
            strengths.append("Strong technical fit with the requirements")

    elif hard_skills_score < _HARD_SKILLS_GAP_THRESHOLD:
        missing = get_missing_skills(persona, job, "Hard", required_only=True)
        if missing:
            # Show up to 3 missing skills
            skill_list = ", ".join(missing[:3])
            gaps.append(f"Missing required skills: {skill_list}")

    # -------------------------------------------------------------------------
    # Experience Analysis (REQ-008 §8.2)
    # -------------------------------------------------------------------------
    experience_score = fit_result.components.get("experience_level", 70.0)

    if experience_score >= _EXPERIENCE_STRENGTH_THRESHOLD:
        years = persona.years_experience
        if years is not None:
            strengths.append(f"Experience level is a perfect match ({years} years)")
        else:
            strengths.append("Experience level matches well")

    elif experience_score < _EXPERIENCE_GAP_THRESHOLD:
        # Determine if under-qualified or over-qualified
        persona_years = persona.years_experience
        job_min = job.years_experience_min
        job_max = job.years_experience_max

        if persona_years is not None:
            # Check under-qualified
            if job_min is not None and persona_years < job_min:
                gaps.append(
                    f"Under-qualified: job wants {job_min}+ years, you have {persona_years}"
                )
            # Check over-qualified (separate condition)
            elif job_max is not None and persona_years > job_max:
                warnings.append(
                    f"May be seen as overqualified ({persona_years} years vs. {job_max} max)"
                )

    # -------------------------------------------------------------------------
    # Stretch Analysis (REQ-008 §8.2)
    # -------------------------------------------------------------------------
    target_skills_score = stretch_result.components.get("target_skills", 50.0)
    target_role_score = stretch_result.components.get("target_role", 50.0)

    if target_skills_score >= _TARGET_SKILLS_STRETCH_THRESHOLD:
        target_matches = get_target_skill_matches(persona, job)
        if target_matches:
            skill_list = ", ".join(target_matches[:3])
            stretch_opportunities.append(f"Exposure to target skills: {skill_list}")
        else:
            stretch_opportunities.append("Good exposure to skills you want to develop")

    if target_role_score >= _TARGET_ROLE_STRETCH_THRESHOLD:
        target_roles = persona.target_roles
        if target_roles:
            stretch_opportunities.append(
                f"Aligns with your target role of {target_roles[0]}"
            )
        else:
            stretch_opportunities.append("Aligns well with your career direction")

    # -------------------------------------------------------------------------
    # Warnings (REQ-008 §8.2)
    # -------------------------------------------------------------------------

    # Salary warning
    if job.salary_max is None:
        warnings.append("Salary not disclosed")

    # Ghost score warning
    if job.ghost_score >= _GHOST_SCORE_WARNING_THRESHOLD:
        warnings.append(f"Ghost risk: {job.ghost_score}% — this posting may be stale")

    # -------------------------------------------------------------------------
    # Summary Generation (REQ-008 §8.2)
    # -------------------------------------------------------------------------
    summary = generate_summary_sentence(
        fit_result.total,
        stretch_result.total,
        strengths,
        gaps,
    )

    return ScoreExplanation(
        summary=summary,
        strengths=strengths,
        gaps=gaps,
        stretch_opportunities=stretch_opportunities,
        warnings=warnings,
    )
