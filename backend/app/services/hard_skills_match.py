"""Hard skills match calculation for Fit Score.

REQ-008 §4.2: Hard Skills Match component (40% of Fit Score).

Compares user's Skill records against job's ExtractedSkill records.
Uses proficiency weighting and skill normalization for accurate matching.

Key formula:
    score = (required_score × 0.80) + (nice_to_have_score × 0.20)

Where required_score and nice_to_have_score are weighted averages (0-100)
based on proficiency match between user skills and job requirements.
"""

from typing import TypedDict

from app.services.fit_score import FIT_NEUTRAL_SCORE

# =============================================================================
# Type Definitions
# =============================================================================


class PersonaSkillInput(TypedDict, total=False):
    """Persona skill input for scoring.

    Matches Skill model fields needed for hard skills calculation.
    """

    skill_name: str
    skill_type: str  # "Hard" or "Soft"
    proficiency: str  # "Learning", "Familiar", "Proficient", "Expert"


class JobSkillInput(TypedDict, total=False):
    """Job skill input for scoring.

    Matches ExtractedSkill schema fields needed for hard skills calculation.
    """

    skill_name: str
    skill_type: str  # "Hard" or "Soft"
    is_required: bool  # True = required, False = nice-to-have
    years_requested: int | None  # Years of experience if specified


# =============================================================================
# Skill Normalization (REQ-008 §4.2.2)
# =============================================================================

# Skill synonym dictionary for common variations
# Maps variations to canonical form
_SKILL_SYNONYMS: dict[str, str] = {
    # JavaScript variations
    "js": "javascript",
    "javascript": "javascript",
    # React variations
    "react.js": "react",
    "reactjs": "react",
    "react": "react",
    # Node.js variations
    "node.js": "nodejs",
    "nodejs": "nodejs",
    "node": "nodejs",
    # AWS variations
    "aws": "aws",
    "amazon web services": "aws",
    # CI/CD variations
    "ci/cd": "ci_cd",
    "cicd": "ci_cd",
    "ci-cd": "ci_cd",
    # TypeScript variations
    "ts": "typescript",
    "typescript": "typescript",
    # Kubernetes variations
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    # PostgreSQL variations
    "postgres": "postgresql",
    "postgresql": "postgresql",
    # MongoDB variations
    "mongo": "mongodb",
    "mongodb": "mongodb",
}


def normalize_skill(skill_name: str) -> str:
    """Normalize skill name for matching.

    REQ-008 §4.2.2: Skill Normalization.

    Handles:
    - Case normalization (lowercase)
    - Whitespace stripping
    - Common synonyms (JS → javascript, AWS → aws, etc.)

    Args:
        skill_name: Raw skill name from user or job.

    Returns:
        Normalized skill name for comparison.
    """
    # Lowercase and strip whitespace
    normalized = skill_name.lower().strip()

    # Check synonym dictionary
    if normalized in _SKILL_SYNONYMS:
        return _SKILL_SYNONYMS[normalized]

    # Return as-is if no synonym found
    return normalized


# =============================================================================
# Proficiency Weighting (REQ-008 §4.2.3)
# =============================================================================

# Map proficiency levels to approximate years of experience
# Used to compare against job requirements
_PROFICIENCY_YEARS: dict[str, float] = {
    "Learning": 0.5,
    "Familiar": 1.5,
    "Proficient": 3.5,
    "Expert": 6.0,
}

# Default years for unknown proficiency (middle ground)
_DEFAULT_PROFICIENCY_YEARS = 2.0

# Penalty per year of gap (15% per year under requirement)
_PENALTY_PER_YEAR = 0.15

# Minimum weight (user still has the skill, just less experience)
_MINIMUM_WEIGHT = 0.2


def get_proficiency_weight(
    persona_proficiency: str,
    job_years_requested: int | None,
) -> float:
    """Calculate proficiency weight for skill match.

    REQ-008 §4.2.3: Proficiency Weighting.

    Returns 0.0-1.0 weight based on how well user's proficiency
    matches job's years requirement.

    | Scenario | Weight |
    |----------|--------|
    | No years specified | 1.0 (full credit) |
    | Meets/exceeds requirement | 1.0 |
    | Below requirement | 1.0 - (gap × 0.15), min 0.2 |

    Args:
        persona_proficiency: User's proficiency level
            ("Learning", "Familiar", "Proficient", "Expert").
        job_years_requested: Job's years requirement, or None if unspecified.

    Returns:
        Weight factor 0.2-1.0 for this skill match.
    """
    # If job doesn't specify years, any proficiency counts as full match
    if job_years_requested is None:
        return 1.0

    # Map proficiency to approximate years
    user_years = _PROFICIENCY_YEARS.get(persona_proficiency, _DEFAULT_PROFICIENCY_YEARS)

    # User meets or exceeds requirement
    if user_years >= job_years_requested:
        return 1.0

    # Calculate penalty based on gap
    # Each year under = 15% penalty, minimum 0.2
    gap = job_years_requested - user_years
    penalty = gap * _PENALTY_PER_YEAR
    return max(_MINIMUM_WEIGHT, 1.0 - penalty)


# =============================================================================
# Hard Skills Score Calculation (REQ-008 §4.2.1)
# =============================================================================

# Maximum skill list size to prevent DoS via large inputs
_MAX_SKILLS = 500


def calculate_hard_skills_score(
    persona_skills: list[PersonaSkillInput],
    job_skills: list[JobSkillInput],
) -> float:
    """Calculate hard skills match score (0-100).

    REQ-008 §4.2.1: Calculation Method.

    Compares user's hard skills against job's hard skill requirements,
    applying proficiency weighting.

    Score formula:
    - Required skills: 80% of component (weighted by proficiency)
    - Nice-to-have skills: 20% of component (bonus points)

    Args:
        persona_skills: List of user's skills matching PersonaSkillInput structure.
        job_skills: List of job's extracted skills matching JobSkillInput structure.

    Returns:
        Hard skills score 0-100.

    Raises:
        ValueError: If skill lists exceed maximum size (_MAX_SKILLS).
    """
    # Defensive size limit to prevent DoS
    if len(persona_skills) > _MAX_SKILLS or len(job_skills) > _MAX_SKILLS:
        msg = f"Skill lists exceed maximum size of {_MAX_SKILLS}"
        raise ValueError(msg)
    # Filter to hard skills only
    required_skills = [
        s
        for s in job_skills
        if s.get("is_required", True) and s.get("skill_type") == "Hard"
    ]
    nice_to_have_skills = [
        s
        for s in job_skills
        if not s.get("is_required", True) and s.get("skill_type") == "Hard"
    ]

    # No hard skills specified → neutral score
    if not required_skills and not nice_to_have_skills:
        return FIT_NEUTRAL_SCORE

    # Build persona skill lookup: {normalized_name: skill}
    persona_skill_map: dict[str, PersonaSkillInput] = {}
    for skill in persona_skills:
        if skill.get("skill_type") == "Hard":
            norm_name = normalize_skill(skill.get("skill_name", ""))
            persona_skill_map[norm_name] = skill

    # Calculate weighted matches for required skills
    required_weighted_score = 0.0
    for job_skill in required_skills:
        norm_name = normalize_skill(job_skill.get("skill_name", ""))
        if norm_name in persona_skill_map:
            persona_skill = persona_skill_map[norm_name]
            weight = get_proficiency_weight(
                persona_proficiency=persona_skill.get("proficiency", ""),
                job_years_requested=job_skill.get("years_requested"),
            )
            required_weighted_score += weight

    # Calculate weighted matches for nice-to-have skills
    nice_weighted_score = 0.0
    for job_skill in nice_to_have_skills:
        norm_name = normalize_skill(job_skill.get("skill_name", ""))
        if norm_name in persona_skill_map:
            persona_skill = persona_skill_map[norm_name]
            weight = get_proficiency_weight(
                persona_proficiency=persona_skill.get("proficiency", ""),
                job_years_requested=job_skill.get("years_requested"),
            )
            nice_weighted_score += weight

    # Required skills are critical (80% of component)
    if required_skills:
        required_score = (required_weighted_score / len(required_skills)) * 80
    else:
        required_score = 80  # No required skills = full credit for required portion

    # Nice-to-have adds bonus (20% of component)
    if nice_to_have_skills:
        nice_score = (nice_weighted_score / len(nice_to_have_skills)) * 20
    else:
        nice_score = 0

    return required_score + nice_score
