"""Unit tests for Missing Data edge cases.

REQ-008 §9.1: Missing Data Edge Cases.

Tests verify that scoring handles incomplete data gracefully:
1. Job has no skills extracted → neutral scores, flag for review
2. Persona has no skills → block scoring (tested at component level)
3. Job experience not specified → neutral (70) for experience component
4. No salary range → pass non-negotiables filter with warning

Design principle from REQ-008 §1.2:
"Graceful degradation — Missing data reduces confidence, does not break scoring."
"""

from app.services.experience_level import calculate_experience_score
from app.services.fit_score import (
    FIT_NEUTRAL_SCORE,
    calculate_fit_score,
)
from app.services.hard_skills_match import calculate_hard_skills_score
from app.services.non_negotiables_filter import (
    NonNegotiablesResult,
    aggregate_filter_results,
    check_industry_exclusions,
    check_minimum_salary,
    check_remote_preference,
    check_visa_sponsorship,
)
from app.services.role_title_match import calculate_role_title_score
from app.services.soft_skills_match import calculate_soft_skills_score
from app.services.stretch_score import (
    STRETCH_NEUTRAL_SCORE,
    calculate_stretch_score,
    calculate_target_role_alignment,
    calculate_target_skills_exposure,
)

# =============================================================================
# Constants for Tests
# =============================================================================

# Default embedding dimension (OpenAI text-embedding-3-small)
EMBEDDING_DIM = 1536


# =============================================================================
# REQ-008 §9.1: Job Has No Skills Extracted
# =============================================================================


class TestJobNoSkillsExtracted:
    """Tests for when job posting has no skills extracted."""

    def test_hard_skills_returns_neutral_when_no_job_skills(self) -> None:
        """REQ-008 §9.1: No job skills → neutral score (70)."""
        persona_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "proficiency": "5+ years"},
            {"skill_name": "FastAPI", "skill_type": "Hard", "proficiency": "3-5 years"},
        ]
        job_skills: list[dict] = []  # No skills extracted

        result = calculate_hard_skills_score(persona_skills, job_skills)

        assert result == FIT_NEUTRAL_SCORE  # 70

    def test_hard_skills_returns_neutral_when_no_required_or_nice_skills(
        self,
    ) -> None:
        """REQ-008 §9.1: Empty job skills list returns neutral."""
        persona_skills = [
            {"skill_name": "React", "skill_type": "Hard", "proficiency": "3-5 years"},
        ]
        # Job has skills but all are soft skills (not hard)
        job_skills = [
            {"skill_name": "Communication", "skill_type": "Soft", "is_required": True},
        ]

        result = calculate_hard_skills_score(persona_skills, job_skills)

        # No hard skills to match → neutral
        assert result == FIT_NEUTRAL_SCORE

    def test_soft_skills_returns_neutral_when_job_embedding_none(self) -> None:
        """REQ-008 §9.1: No job soft skills embedding → neutral score (70)."""
        persona_embedding = [0.1] * EMBEDDING_DIM
        job_embedding = None  # No embedding available

        result = calculate_soft_skills_score(persona_embedding, job_embedding)

        assert result == FIT_NEUTRAL_SCORE

    def test_target_skills_exposure_returns_20_when_no_job_skills(self) -> None:
        """REQ-008 §9.1: No job skills → low stretch score (20)."""
        target_skills = ["Kubernetes", "GraphQL"]
        job_skills: list[str] = []  # No skills extracted

        result = calculate_target_skills_exposure(target_skills, job_skills)

        # No skills to match against → returns 20 (penalty for zero matches)
        assert result == 20


class TestPersonaNoSkills:
    """Tests for when persona has no skills.

    REQ-008 §9.1: "Persona has no skills → Block scoring, prompt user
    to complete onboarding."

    Note: The blocking behavior is implemented at the Strategist Agent level
    (REQ-007 §7), not in the component functions. Component functions return
    scores based on what they receive - the orchestration layer blocks scoring.
    """

    def test_hard_skills_returns_zero_when_persona_has_no_hard_skills(self) -> None:
        """Component-level: no persona skills → low score (0)."""
        persona_skills: list[dict] = []  # No skills
        job_skills = [
            {"skill_name": "Python", "skill_type": "Hard", "is_required": True},
            {"skill_name": "FastAPI", "skill_type": "Hard", "is_required": True},
        ]

        result = calculate_hard_skills_score(persona_skills, job_skills)

        # No matches on required skills → 0
        # Score formula: 80% * required_score + 20% * nice_to_have_score
        # Required = (0 / 2) * 80 = 0, Nice-to-have = 0 (none listed)
        # Result = 0 + 0 = 0
        assert result == 0.0

    def test_soft_skills_returns_neutral_when_persona_embedding_none(
        self,
    ) -> None:
        """REQ-008 §9.1: No persona soft skills embedding → neutral (70)."""
        persona_embedding = None
        job_embedding = [0.2] * EMBEDDING_DIM

        result = calculate_soft_skills_score(persona_embedding, job_embedding)

        assert result == FIT_NEUTRAL_SCORE

    def test_target_skills_returns_neutral_when_no_target_skills(self) -> None:
        """REQ-008 §9.1: No target skills defined → neutral stretch (50)."""
        target_skills: list[str] = []  # No target skills
        job_skills = ["Kubernetes", "Python"]

        result = calculate_target_skills_exposure(target_skills, job_skills)

        assert result == STRETCH_NEUTRAL_SCORE  # 50


# =============================================================================
# REQ-008 §9.1: Job Experience Not Specified
# =============================================================================


class TestJobExperienceNotSpecified:
    """Tests for when job doesn't specify experience requirements."""

    def test_experience_returns_neutral_when_no_job_requirements(self) -> None:
        """REQ-008 §9.1: No experience requirements → neutral score (70)."""
        user_years = 5
        job_min_years = None
        job_max_years = None

        result = calculate_experience_score(user_years, job_min_years, job_max_years)

        assert result == FIT_NEUTRAL_SCORE

    def test_experience_returns_neutral_when_both_bounds_none(self) -> None:
        """Both min and max None → neutral score."""
        result = calculate_experience_score(
            user_years=10,
            job_min_years=None,
            job_max_years=None,
        )

        assert result == FIT_NEUTRAL_SCORE

    def test_experience_handles_user_years_none(self) -> None:
        """REQ-008 §9.1: User years is None → treated as 0."""
        user_years = None
        job_min_years = 5
        job_max_years = 10

        result = calculate_experience_score(user_years, job_min_years, job_max_years)

        # User with 0 years vs 5-10 requirement → under-qualified penalty
        assert result < FIT_NEUTRAL_SCORE


# =============================================================================
# REQ-008 §9.1: No Salary Range
# =============================================================================


class TestNoSalaryRange:
    """Tests for when job doesn't disclose salary range."""

    def test_filter_passes_when_salary_undisclosed(self) -> None:
        """REQ-008 §9.1: No salary → pass filter, add warning."""
        result = check_minimum_salary(
            minimum_base_salary=80_000,
            job_salary_max=None,  # Undisclosed
        )

        assert result.passed is True
        assert "Salary not disclosed" in result.warnings

    def test_filter_passes_with_salary_warning_only(self) -> None:
        """Undisclosed salary adds warning but doesn't block."""
        result = check_minimum_salary(
            minimum_base_salary=150_000,  # High requirement
            job_salary_max=None,  # Undisclosed
        )

        # Still passes even with high salary requirement
        assert result.passed is True
        assert "Salary not disclosed" in result.warnings


# =============================================================================
# Role Title Missing Data
# =============================================================================


class TestRoleTitleMissingData:
    """Tests for role title match with missing data."""

    def test_role_title_returns_neutral_when_job_title_empty(self) -> None:
        """REQ-008 §9.1: Empty job title → neutral score (70)."""
        result = calculate_role_title_score(
            current_role="Senior Software Engineer",
            work_history_titles=["Lead Developer"],
            job_title="",  # Empty title
            user_titles_embedding=None,
            job_title_embedding=None,
        )

        assert result == FIT_NEUTRAL_SCORE

    def test_role_title_returns_neutral_when_user_has_no_titles(self) -> None:
        """REQ-008 §9.1: User has no titles → neutral score (70)."""
        result = calculate_role_title_score(
            current_role=None,
            work_history_titles=[],  # No titles
            job_title="Senior Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )

        assert result == FIT_NEUTRAL_SCORE

    def test_role_title_returns_neutral_when_embeddings_missing(self) -> None:
        """No embeddings available → falls back to normalization (or neutral)."""
        result = calculate_role_title_score(
            current_role="Backend Engineer",
            work_history_titles=[],
            job_title="Full Stack Developer",  # No exact match
            user_titles_embedding=None,  # No embeddings
            job_title_embedding=None,  # No embeddings
        )

        # No exact match, no embeddings → neutral
        assert result == FIT_NEUTRAL_SCORE


# =============================================================================
# Aggregate Score with Missing Data
# =============================================================================


class TestFitScoreAggregateWithMissingData:
    """Tests for Fit Score aggregation when components have neutral values."""

    def test_all_neutral_components_produce_neutral_total(self) -> None:
        """All components at neutral (70) → total is 70."""
        result = calculate_fit_score(
            hard_skills=FIT_NEUTRAL_SCORE,
            soft_skills=FIT_NEUTRAL_SCORE,
            experience_level=FIT_NEUTRAL_SCORE,
            role_title=FIT_NEUTRAL_SCORE,
            location_logistics=FIT_NEUTRAL_SCORE,
        )

        assert result.total == FIT_NEUTRAL_SCORE  # 70

    def test_mixed_scores_with_neutral_components(self) -> None:
        """Some strong scores with neutral for missing data."""
        result = calculate_fit_score(
            hard_skills=85.0,  # Strong
            soft_skills=FIT_NEUTRAL_SCORE,  # Missing data
            experience_level=90.0,  # Strong
            role_title=FIT_NEUTRAL_SCORE,  # Missing data
            location_logistics=FIT_NEUTRAL_SCORE,  # Missing data
        )

        # Expected: 85*0.4 + 70*0.15 + 90*0.25 + 70*0.1 + 70*0.1
        # = 34 + 10.5 + 22.5 + 7 + 7 = 81
        assert result.total == 81

    def test_strong_scores_offset_neutral_components(self) -> None:
        """Strong scores in some components can offset neutral in others."""
        result = calculate_fit_score(
            hard_skills=95.0,  # Very strong (40% weight)
            soft_skills=FIT_NEUTRAL_SCORE,  # Neutral
            experience_level=100.0,  # Perfect (25% weight)
            role_title=FIT_NEUTRAL_SCORE,  # Neutral
            location_logistics=FIT_NEUTRAL_SCORE,  # Neutral
        )

        # Expected: 95*0.4 + 70*0.15 + 100*0.25 + 70*0.1 + 70*0.1
        # = 38 + 10.5 + 25 + 7 + 7 = 87.5 → 88
        assert result.total == 88


class TestStretchScoreAggregateWithMissingData:
    """Tests for Stretch Score aggregation when components have neutral values."""

    def test_all_neutral_components_produce_neutral_total(self) -> None:
        """All components at neutral (50) → total is 50."""
        result = calculate_stretch_score(
            target_role=STRETCH_NEUTRAL_SCORE,
            target_skills=STRETCH_NEUTRAL_SCORE,
            growth_trajectory=STRETCH_NEUTRAL_SCORE,
        )

        assert result.total == STRETCH_NEUTRAL_SCORE  # 50

    def test_mixed_scores_with_neutral_components(self) -> None:
        """Some strong scores with neutral for missing data."""
        result = calculate_stretch_score(
            target_role=80.0,  # Good alignment
            target_skills=STRETCH_NEUTRAL_SCORE,  # No target skills defined
            growth_trajectory=STRETCH_NEUTRAL_SCORE,  # Can't infer level
        )

        # Expected: 80*0.5 + 50*0.4 + 50*0.1 = 40 + 20 + 5 = 65
        assert result.total == 65


# =============================================================================
# Edge Case: Both Persona and Job Missing Data
# =============================================================================


class TestBothPersonaAndJobMissingData:
    """Tests for when both persona and job have missing data."""

    def test_soft_skills_neutral_when_both_embeddings_none(self) -> None:
        """Both embeddings None → neutral score (70)."""
        result = calculate_soft_skills_score(
            persona_soft_embedding=None,
            job_soft_embedding=None,
        )

        assert result == FIT_NEUTRAL_SCORE

    def test_experience_neutral_when_both_missing(self) -> None:
        """User years None and job requirements None → neutral."""
        result = calculate_experience_score(
            user_years=None,
            job_min_years=None,
            job_max_years=None,
        )

        # User years None → treated as 0, but no requirements → neutral
        assert result == FIT_NEUTRAL_SCORE


# =============================================================================
# Stretch Score Target Role Missing Data
# =============================================================================


class TestStretchTargetRoleMissingData:
    """Tests for target role alignment with missing data."""

    def test_target_role_neutral_when_no_target_roles(self) -> None:
        """REQ-008 §9.1: No target roles defined → neutral (50)."""
        result = calculate_target_role_alignment(
            target_roles=[],
            job_title="Senior Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )

        assert result == STRETCH_NEUTRAL_SCORE

    def test_target_role_neutral_when_job_title_empty(self) -> None:
        """No job title → neutral stretch score."""
        result = calculate_target_role_alignment(
            target_roles=["Engineering Manager", "Tech Lead"],
            job_title="",
            target_roles_embedding=None,
            job_title_embedding=None,
        )

        assert result == STRETCH_NEUTRAL_SCORE

    def test_target_role_neutral_when_embeddings_missing(self) -> None:
        """No embeddings available → neutral (unless exact match)."""
        result = calculate_target_role_alignment(
            target_roles=["Data Scientist"],
            job_title="Machine Learning Engineer",  # No exact match
            target_roles_embedding=None,  # No embeddings
            job_title_embedding=None,  # No embeddings
        )

        # No embeddings, no exact match → neutral
        assert result == STRETCH_NEUTRAL_SCORE


# =============================================================================
# Non-Negotiables Filter Other Missing Data
# =============================================================================


class TestNonNegotiablesOtherMissingData:
    """Tests for non-negotiables filter with various missing data scenarios."""

    def test_filter_passes_when_work_model_undisclosed_onsite_ok(self) -> None:
        """Undisclosed work model → assume Onsite (conservative)."""
        result = check_remote_preference(
            remote_preference="Onsite OK",  # User accepts Onsite
            job_work_model=None,  # Undisclosed
        )

        # "Onsite OK" always passes
        assert result.passed is True

    def test_filter_fails_when_work_model_undisclosed_remote_only(self) -> None:
        """User only accepts Remote, work model undisclosed → fail."""
        result = check_remote_preference(
            remote_preference="Remote Only",  # Remote only
            job_work_model=None,  # Undisclosed → assumes Onsite
        )

        # Assumes Onsite, user only wants Remote → fails
        assert result.passed is False

    def test_filter_passes_when_visa_sponsorship_undisclosed(self) -> None:
        """REQ-008 §9.1: Undisclosed visa sponsorship → pass with warning."""
        result = check_visa_sponsorship(
            visa_sponsorship_required=True,  # User needs sponsorship
            job_visa_sponsorship=None,  # Undisclosed
        )

        # Benefit of doubt for undisclosed
        assert result.passed is True
        assert any(
            "visa" in w.lower() or "sponsorship" in w.lower() for w in result.warnings
        )

    def test_filter_passes_when_industry_undisclosed(self) -> None:
        """REQ-008 §9.1: Undisclosed industry → pass with warning."""
        result = check_industry_exclusions(
            industry_exclusions=["Oil", "Defense"],  # User exclusions
            job_industry=None,  # Undisclosed
        )

        assert result.passed is True
        # Should have warning about undisclosed industry
        assert any("industry" in w.lower() for w in result.warnings)


# =============================================================================
# Aggregate Filter with Multiple Missing Values
# =============================================================================


class TestAggregateFilterWithMissingData:
    """Tests for aggregating filter results with missing data."""

    def test_aggregate_multiple_warnings(self) -> None:
        """Multiple undisclosed fields → aggregate all warnings."""
        salary_result = check_minimum_salary(
            minimum_base_salary=100_000,
            job_salary_max=None,  # Undisclosed
        )
        visa_result = check_visa_sponsorship(
            visa_sponsorship_required=True,
            job_visa_sponsorship=None,  # Undisclosed
        )
        industry_result = check_industry_exclusions(
            industry_exclusions=["Finance"],
            job_industry=None,  # Undisclosed
        )

        aggregate = aggregate_filter_results(
            [salary_result, visa_result, industry_result]
        )

        assert aggregate.passed is True  # All pass with warnings
        assert len(aggregate.warnings) >= 3  # At least 3 warnings

    def test_aggregate_passes_when_all_pass_with_warnings(self) -> None:
        """Aggregate of passing results with warnings → passes with all warnings."""
        results = [
            NonNegotiablesResult(passed=True, warnings=["Warning 1"]),
            NonNegotiablesResult(passed=True, warnings=["Warning 2"]),
        ]

        aggregate = aggregate_filter_results(results)

        assert aggregate.passed is True
        assert len(aggregate.warnings) == 2

    def test_aggregate_fails_if_any_fails(self) -> None:
        """Aggregate fails if any individual filter fails."""
        results = [
            NonNegotiablesResult(passed=True, warnings=["Salary not disclosed"]),
            NonNegotiablesResult(
                passed=False,
                failed_reasons=["Remote only but job is Onsite"],
            ),
        ]

        aggregate = aggregate_filter_results(results)

        assert aggregate.passed is False
        assert len(aggregate.failed_reasons) == 1
        assert len(aggregate.warnings) == 1
