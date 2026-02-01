"""Unit tests for hard skills match calculation.

REQ-008 §4.2: Hard Skills Match component (40% of Fit Score).

Tests cover:
- Skill normalization (synonyms, case, punctuation)
- Proficiency weighting (user experience vs. job requirements)
- Hard skills score calculation (required vs. nice-to-have)
"""

import pytest

from app.services.hard_skills_match import (
    calculate_hard_skills_score,
    get_proficiency_weight,
    normalize_skill,
)

# =============================================================================
# Skill Normalization Tests (REQ-008 §4.2.2)
# =============================================================================


class TestNormalizeSkill:
    """Tests for skill name normalization."""

    def test_lowercase_and_strip(self) -> None:
        """Normalizes to lowercase and strips whitespace."""
        assert normalize_skill("  Python  ") == "python"

    def test_common_javascript_variations(self) -> None:
        """Handles JavaScript/JS variations."""
        assert normalize_skill("JavaScript") == "javascript"
        assert normalize_skill("Javascript") == "javascript"
        assert normalize_skill("JS") == "javascript"
        assert normalize_skill("js") == "javascript"

    def test_common_react_variations(self) -> None:
        """Handles React.js/ReactJS variations."""
        assert normalize_skill("React.js") == "react"
        assert normalize_skill("ReactJS") == "react"
        assert normalize_skill("React") == "react"
        assert normalize_skill("react.js") == "react"

    def test_common_aws_variations(self) -> None:
        """Handles AWS/Amazon Web Services variations."""
        assert normalize_skill("AWS") == "aws"
        assert normalize_skill("Amazon Web Services") == "aws"
        assert normalize_skill("aws") == "aws"

    def test_cicd_variations(self) -> None:
        """Handles CI/CD punctuation variations."""
        assert normalize_skill("CI/CD") == "ci_cd"
        assert normalize_skill("CICD") == "ci_cd"
        assert normalize_skill("CI-CD") == "ci_cd"
        assert normalize_skill("ci/cd") == "ci_cd"

    def test_nodejs_variations(self) -> None:
        """Handles Node.js variations."""
        assert normalize_skill("Node.js") == "nodejs"
        assert normalize_skill("NodeJS") == "nodejs"
        assert normalize_skill("Node") == "nodejs"

    def test_unknown_skill_lowercased(self) -> None:
        """Unknown skills are lowercased but not transformed."""
        assert normalize_skill("ObscureFramework") == "obscureframework"
        assert normalize_skill("My Custom Skill") == "my custom skill"


# =============================================================================
# Proficiency Weighting Tests (REQ-008 §4.2.3)
# =============================================================================


class TestGetProficiencyWeight:
    """Tests for proficiency-to-experience weighting."""

    def test_no_years_requested_full_weight(self) -> None:
        """If job doesn't specify years, any proficiency counts as full match."""
        assert get_proficiency_weight("Learning", None) == 1.0
        assert get_proficiency_weight("Familiar", None) == 1.0
        assert get_proficiency_weight("Proficient", None) == 1.0
        assert get_proficiency_weight("Expert", None) == 1.0

    def test_expert_meets_high_requirements(self) -> None:
        """Expert (5+ years) meets high experience requirements."""
        assert get_proficiency_weight("Expert", 5) == 1.0
        assert get_proficiency_weight("Expert", 6) == 1.0
        # Expert (6 years equivalent) should fully meet 5+ years
        assert get_proficiency_weight("Expert", 4) == 1.0

    def test_proficient_partial_for_high_requirements(self) -> None:
        """Proficient (2-5 years) gets partial credit for 5+ requirements."""
        # Proficient = 3.5 years, job wants 5 years
        # Gap = 1.5 years → penalty = 1.5 * 0.15 = 0.225
        # Weight = 1.0 - 0.225 = 0.775
        weight = get_proficiency_weight("Proficient", 5)
        assert weight == pytest.approx(0.775, abs=0.01)

    def test_familiar_larger_penalty(self) -> None:
        """Familiar (1-2 years) gets larger penalty for senior requirements."""
        # Familiar = 1.5 years, job wants 5 years
        # Gap = 3.5 years → penalty = 3.5 * 0.15 = 0.525
        # Weight = 1.0 - 0.525 = 0.475
        weight = get_proficiency_weight("Familiar", 5)
        assert weight == pytest.approx(0.475, abs=0.01)

    def test_learning_minimum_weight(self) -> None:
        """Learning gets minimum weight (0.2) for high requirements."""
        # Learning = 0.5 years, job wants 5 years
        # Gap = 4.5 years → penalty = 4.5 * 0.15 = 0.675
        # Weight = max(0.2, 1.0 - 0.675) = max(0.2, 0.325) = 0.325
        weight = get_proficiency_weight("Learning", 5)
        assert weight == pytest.approx(0.325, abs=0.01)

    def test_learning_capped_at_minimum(self) -> None:
        """Learning weight capped at 0.2 for very high requirements."""
        # Learning = 0.5 years, job wants 10 years
        # Gap = 9.5 years → penalty = 9.5 * 0.15 = 1.425
        # Weight = max(0.2, 1.0 - 1.425) = max(0.2, -0.425) = 0.2
        weight = get_proficiency_weight("Learning", 10)
        assert weight == 0.2

    def test_unknown_proficiency_defaults_to_middle(self) -> None:
        """Unknown proficiency level defaults to ~2 years equivalent."""
        # Unknown defaults to 2.0 years, job wants 3 years
        # Gap = 1 year → penalty = 1 * 0.15 = 0.15
        # Weight = 1.0 - 0.15 = 0.85
        weight = get_proficiency_weight("SomethingElse", 3)
        assert weight == pytest.approx(0.85, abs=0.01)


# =============================================================================
# Hard Skills Score Calculation Tests (REQ-008 §4.2.1)
# =============================================================================


class TestCalculateHardSkillsScore:
    """Tests for the main hard skills score calculation."""

    def test_no_job_skills_returns_neutral(self) -> None:
        """Job with no skills specified returns neutral score (70)."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Expert"},
        ]
        job_skills: list[dict] = []

        score = calculate_hard_skills_score(persona_skills, job_skills)
        assert score == 70.0

    def test_perfect_match_required_skills(self) -> None:
        """Perfect match on all required skills returns 100."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Expert"},
            {"skill_name": "SQL", "skill_type": "Hard", "proficiency": "Expert"},
        ]
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
            {
                "skill_name": "SQL",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Required: 2/2 = 100% → 80 points
        # Nice-to-have: none → 0 points
        # Total: 80
        assert score == 80.0

    def test_perfect_match_with_nice_to_have(self) -> None:
        """Perfect match including nice-to-have skills."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Expert"},
            {"skill_name": "Docker", "skill_type": "Hard", "proficiency": "Proficient"},
        ]
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
            {
                "skill_name": "Docker",
                "skill_type": "Hard",
                "is_required": False,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Required: 1/1 = 100% → 80 points
        # Nice-to-have: 1/1 = 100% → 20 points
        # Total: 100
        assert score == 100.0

    def test_missing_required_skills(self) -> None:
        """Missing required skills reduces score significantly."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Expert"},
        ]
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
            {
                "skill_name": "Go",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Required: 1/2 = 50% → 40 points
        # Nice-to-have: none → 0 points
        # Total: 40
        assert score == 40.0

    def test_proficiency_weighting_applied(self) -> None:
        """Proficiency weighting reduces score for underqualified skills."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Familiar"},
            {"skill_name": "SQL", "skill_type": "Hard", "proficiency": "Expert"},
        ]
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": 5,
            },
            {
                "skill_name": "SQL",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Python: Familiar (1.5y) vs 5y → weight 0.475
        # SQL: Expert, no years → weight 1.0
        # Required weighted: (0.475 + 1.0) / 2 = 0.7375 → 59 points
        # Total: 59
        assert score == pytest.approx(59.0, abs=1.0)

    def test_skill_normalization_matches_variations(self) -> None:
        """Skill variations are matched via normalization."""
        persona_skills = [
            {"skill_name": "JavaScript", "skill_type": "Hard", "proficiency": "Expert"},
            {
                "skill_name": "ReactJS",
                "skill_type": "Hard",
                "proficiency": "Proficient",
            },
        ]
        job_skills = [
            {
                "skill_name": "JS",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
            {
                "skill_name": "React.js",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # JS → javascript matches JavaScript → javascript
        # React.js → react matches ReactJS → react
        # Required: 2/2 = 100% → 80 points
        assert score == 80.0

    def test_ignores_soft_skills(self) -> None:
        """Only hard skills are counted, soft skills ignored."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Expert"},
            {"skill_name": "Leadership", "skill_type": "Soft", "proficiency": "Expert"},
        ]
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
            {
                "skill_name": "Leadership",
                "skill_type": "Soft",
                "is_required": True,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Only Hard skills counted: Python matched
        # Required hard: 1/1 = 100% → 80 points
        # Soft skills are separate component (§4.3)
        assert score == 80.0

    def test_only_nice_to_have_no_required(self) -> None:
        """When job has only nice-to-have skills, required gets full credit."""
        persona_skills = [
            {"skill_name": "Docker", "skill_type": "Hard", "proficiency": "Proficient"},
        ]
        job_skills = [
            {
                "skill_name": "Docker",
                "skill_type": "Hard",
                "is_required": False,
                "years_requested": None,
            },
            {
                "skill_name": "Kubernetes",
                "skill_type": "Hard",
                "is_required": False,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # No required → 80 points (full credit)
        # Nice-to-have: 1/2 = 50% → 10 points
        # Total: 90
        assert score == 90.0

    def test_empty_persona_skills(self) -> None:
        """Persona with no skills scores 0 for required, full for no-required."""
        persona_skills: list[dict] = []
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Required: 0/1 = 0% → 0 points
        # Nice-to-have: none → 0 points
        # Total: 0
        assert score == 0.0

    def test_worked_example_from_spec(self) -> None:
        """Verify worked example from REQ-008 §4.2.1."""
        # Job requires: Python (5+ years, required), SQL (required),
        # Kubernetes (nice-to-have)
        # User has: Python (Familiar), SQL (Expert), Docker (Expert)
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "Familiar"},
            {"skill_name": "SQL", "skill_type": "Hard", "proficiency": "Expert"},
            {"skill_name": "Docker", "skill_type": "Hard", "proficiency": "Expert"},
        ]
        job_skills = [
            {
                "skill_name": "Python",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": 5,
            },
            {
                "skill_name": "SQL",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            },
            {
                "skill_name": "Kubernetes",
                "skill_type": "Hard",
                "is_required": False,
                "years_requested": None,
            },
        ]

        score = calculate_hard_skills_score(persona_skills, job_skills)
        # Python: Familiar (1.5y) vs 5y → weight ~0.475
        # SQL: Expert, no years → weight 1.0
        # Required weighted: (0.475 + 1.0) / 2 = 0.7375 → 59 points
        # Kubernetes: missing → 0/1 = 0% → 0 bonus points
        # Total: ~59
        assert score == pytest.approx(59.0, abs=1.0)

    def test_rejects_oversized_persona_skills_list(self) -> None:
        """Raises ValueError if persona_skills exceeds max size."""
        # Create list exceeding _MAX_SKILLS (500)
        oversized_persona = [
            {"skill_name": f"Skill{i}", "skill_type": "Hard", "proficiency": "Expert"}
            for i in range(501)
        ]
        job_skills: list[dict] = []

        with pytest.raises(ValueError, match="exceed maximum size"):
            calculate_hard_skills_score(oversized_persona, job_skills)

    def test_rejects_oversized_job_skills_list(self) -> None:
        """Raises ValueError if job_skills exceeds max size."""
        persona_skills: list[dict] = []
        # Create list exceeding _MAX_SKILLS (500)
        oversized_job = [
            {
                "skill_name": f"Skill{i}",
                "skill_type": "Hard",
                "is_required": True,
                "years_requested": None,
            }
            for i in range(501)
        ]

        with pytest.raises(ValueError, match="exceed maximum size"):
            calculate_hard_skills_score(persona_skills, oversized_job)
