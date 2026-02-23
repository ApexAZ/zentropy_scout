"""Unit tests for Explanation Generation Logic.

REQ-008 §8.2: Explanation Generation Logic.

Tests cover:
- Strengths populated based on high component scores
- Gaps populated based on low component scores
- Stretch opportunities populated based on stretch component scores
- Warnings populated based on job attributes
- Summary generation based on overall scores
- Edge cases (missing data, neutral scores)
"""

import pytest

from app.services.explanation_generation import (
    generate_explanation,
    generate_summary_sentence,
    get_matched_skills,
    get_missing_skills,
    get_target_skill_matches,
)
from app.services.fit_score import FitScoreResult
from app.services.score_explanation import ScoreExplanation
from app.services.stretch_score import StretchScoreResult

# =============================================================================
# Test Data Fixtures
# =============================================================================


def make_fit_result(
    hard_skills: float = 70.0,
    soft_skills: float = 70.0,
    experience_level: float = 70.0,
    role_title: float = 70.0,
    location_logistics: float = 70.0,
) -> FitScoreResult:
    """Create a FitScoreResult with specified component scores."""
    components = {
        "hard_skills": hard_skills,
        "soft_skills": soft_skills,
        "experience_level": experience_level,
        "role_title": role_title,
        "location_logistics": location_logistics,
    }
    weights = {
        "hard_skills": 0.40,
        "soft_skills": 0.15,
        "experience_level": 0.25,
        "role_title": 0.10,
        "location_logistics": 0.10,
    }
    total = round(sum(components[k] * weights[k] for k in components))
    return FitScoreResult(total=total, components=components, weights=weights)


def make_stretch_result(
    target_role: float = 50.0,
    target_skills: float = 50.0,
    growth_trajectory: float = 50.0,
) -> StretchScoreResult:
    """Create a StretchScoreResult with specified component scores."""
    components = {
        "target_role": target_role,
        "target_skills": target_skills,
        "growth_trajectory": growth_trajectory,
    }
    weights = {
        "target_role": 0.50,
        "target_skills": 0.40,
        "growth_trajectory": 0.10,
    }
    total = round(sum(components[k] * weights[k] for k in components))
    return StretchScoreResult(total=total, components=components, weights=weights)


# =============================================================================
# Minimal Data Classes for Testing (mimic model attributes)
# =============================================================================


class MockSkill:
    """Mock persona skill for testing."""

    def __init__(self, skill_name: str, skill_type: str = "Hard"):
        self.skill_name = skill_name
        self.skill_type = skill_type


class MockExtractedSkill:
    """Mock job extracted skill for testing."""

    def __init__(
        self, skill_name: str, skill_type: str = "Hard", is_required: bool = True
    ):
        self.skill_name = skill_name
        self.skill_type = skill_type
        self.is_required = is_required


class MockPersona:
    """Mock persona for testing explanation generation."""

    def __init__(
        self,
        years_experience: int | None = 5,
        current_role: str | None = "Software Engineer",
        target_roles: list[str] | None = None,
        target_skills: list[str] | None = None,
        skills: list[MockSkill] | None = None,
    ):
        self.years_experience = years_experience
        self.current_role = current_role
        self.target_roles = target_roles or []
        self.target_skills = target_skills or []
        self.skills = skills or []


class MockJobPosting:
    """Mock job posting for testing explanation generation."""

    def __init__(
        self,
        job_title: str = "Software Engineer",
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        salary_max: int | None = 150000,
        ghost_score: int = 0,
        extracted_skills: list[MockExtractedSkill] | None = None,
    ):
        self.job_title = job_title
        self.years_experience_min = years_experience_min
        self.years_experience_max = years_experience_max
        self.salary_max = salary_max
        self.ghost_score = ghost_score
        self.extracted_skills = extracted_skills or []


# =============================================================================
# Strengths Population Tests (REQ-008 §8.2)
# =============================================================================


class TestStrengthsFromHardSkills:
    """Tests for hard skills strength population."""

    def test_high_hard_skills_adds_strength(self) -> None:
        """Hard skills >= 80 adds strength to explanation."""
        fit_result = make_fit_result(hard_skills=85.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(
            skills=[
                MockSkill("Python", "Hard"),
                MockSkill("SQL", "Hard"),
                MockSkill("Docker", "Hard"),
            ]
        )
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Python", "Hard"),
                MockExtractedSkill("SQL", "Hard"),
            ]
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.strengths) >= 1
        # Should mention technical fit
        assert any("technical fit" in s.lower() for s in explanation.strengths)

    def test_hard_skills_below_80_no_strength(self) -> None:
        """Hard skills < 80 does not add technical fit strength."""
        fit_result = make_fit_result(hard_skills=75.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(extracted_skills=[MockExtractedSkill("Python", "Hard")])

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should NOT contain technical fit strength
        assert not any("technical fit" in s.lower() for s in explanation.strengths)


class TestStrengthsFromExperience:
    """Tests for experience level strength population."""

    def test_high_experience_adds_strength(self) -> None:
        """Experience >= 90 adds perfect match strength."""
        fit_result = make_fit_result(experience_level=95.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(years_experience=7)
        job = MockJobPosting()

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.strengths) >= 1
        # Should mention experience match
        assert any(
            "experience" in s.lower() and "match" in s.lower()
            for s in explanation.strengths
        )


# =============================================================================
# Gaps Population Tests (REQ-008 §8.2)
# =============================================================================


class TestGapsFromHardSkills:
    """Tests for hard skills gap population."""

    def test_low_hard_skills_adds_gap(self) -> None:
        """Hard skills < 50 adds gap for missing required skills."""
        fit_result = make_fit_result(hard_skills=40.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Kubernetes", "Hard", is_required=True),
                MockExtractedSkill("Terraform", "Hard", is_required=True),
            ]
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.gaps) >= 1
        # Should mention missing required skills
        assert any(
            "missing" in g.lower() or "required" in g.lower() for g in explanation.gaps
        )

    def test_hard_skills_above_50_no_skill_gap(self) -> None:
        """Hard skills >= 50 does not add missing skills gap."""
        fit_result = make_fit_result(hard_skills=60.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(extracted_skills=[MockExtractedSkill("Python", "Hard")])

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should NOT contain missing required skills gap
        assert not any("missing required skill" in g.lower() for g in explanation.gaps)


class TestGapsFromExperience:
    """Tests for experience level gap population."""

    def test_underqualified_adds_gap(self) -> None:
        """Experience < 60 with fewer years than required adds gap."""
        fit_result = make_fit_result(experience_level=45.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(years_experience=3)
        job = MockJobPosting(years_experience_min=7)

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.gaps) >= 1
        # Should mention under-qualified
        assert any(
            "under-qualified" in g.lower() or "under qualified" in g.lower()
            for g in explanation.gaps
        )


# =============================================================================
# Stretch Opportunities Tests (REQ-008 §8.2)
# =============================================================================


class TestStretchOpportunitiesFromTargetSkills:
    """Tests for target skills stretch opportunity population."""

    def test_high_target_skills_adds_stretch(self) -> None:
        """Target skills >= 75 adds stretch opportunity."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result(target_skills=80.0)

        persona = MockPersona(target_skills=["Machine Learning", "Kubernetes"])
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Machine Learning", "Hard"),
                MockExtractedSkill("Python", "Hard"),
            ]
        )

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.stretch_opportunities) >= 1
        # Should mention target skills exposure
        assert any(
            "target skill" in s.lower() or "exposure" in s.lower()
            for s in explanation.stretch_opportunities
        )


class TestStretchOpportunitiesFromTargetRole:
    """Tests for target role stretch opportunity population."""

    def test_high_target_role_adds_stretch(self) -> None:
        """Target role >= 80 adds stretch opportunity."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result(target_role=85.0)

        persona = MockPersona(target_roles=["Senior Engineer", "Tech Lead"])
        job = MockJobPosting(job_title="Senior Software Engineer")

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.stretch_opportunities) >= 1
        # Should mention target role alignment
        assert any(
            "target role" in s.lower() or "aligns" in s.lower()
            for s in explanation.stretch_opportunities
        )


# =============================================================================
# Warnings Population Tests (REQ-008 §8.2)
# =============================================================================


class TestWarningsFromSalary:
    """Tests for salary warning population."""

    def test_undisclosed_salary_adds_warning(self) -> None:
        """Job with no salary_max adds warning."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        persona = MockPersona()
        job = MockJobPosting(salary_max=None)

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.warnings) >= 1
        assert any("salary" in w.lower() for w in explanation.warnings)


class TestWarningsFromGhostScore:
    """Tests for ghost score warning population."""

    def test_high_ghost_score_adds_warning(self) -> None:
        """Ghost score >= 60 adds warning."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        persona = MockPersona()
        job = MockJobPosting(ghost_score=65)

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.warnings) >= 1
        assert any("ghost" in w.lower() for w in explanation.warnings)

    def test_low_ghost_score_no_warning(self) -> None:
        """Ghost score < 60 does not add warning."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        persona = MockPersona()
        job = MockJobPosting(ghost_score=30)

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert not any("ghost" in w.lower() for w in explanation.warnings)


class TestWarningsFromOverqualified:
    """Tests for overqualified warning population."""

    def test_overqualified_adds_warning(self) -> None:
        """Experience < 60 with more years than max adds warning."""
        fit_result = make_fit_result(experience_level=55.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(years_experience=12)
        job = MockJobPosting(years_experience_max=5)

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert len(explanation.warnings) >= 1
        assert any("overqualified" in w.lower() for w in explanation.warnings)


# =============================================================================
# Summary Generation Tests (REQ-008 §8.2)
# =============================================================================


class TestSummaryGeneration:
    """Tests for summary sentence generation."""

    def test_summary_included_in_result(self) -> None:
        """Explanation always includes a summary."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        persona = MockPersona()
        job = MockJobPosting()

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        assert explanation.summary is not None
        assert len(explanation.summary) > 0

    def test_summary_reflects_fit_score(self) -> None:
        """Summary reflects overall fit quality."""
        # High fit score
        high_fit = make_fit_result(
            hard_skills=90.0, experience_level=90.0, soft_skills=90.0
        )
        stretch_result = make_stretch_result()

        persona = MockPersona()
        job = MockJobPosting()

        explanation = generate_explanation(high_fit, stretch_result, persona, job)

        # High fit should produce positive summary
        assert (
            "strong" in explanation.summary.lower()
            or "good" in explanation.summary.lower()
        )


# =============================================================================
# Helper Function Tests (REQ-008 §8.2)
# =============================================================================


class TestGetMatchedSkills:
    """Tests for get_matched_skills helper."""

    def test_returns_matching_hard_skills(self) -> None:
        """Returns skills that exist in both persona and job."""
        persona = MockPersona(
            skills=[
                MockSkill("Python", "Hard"),
                MockSkill("SQL", "Hard"),
                MockSkill("Leadership", "Soft"),
            ]
        )
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Python", "Hard"),
                MockExtractedSkill("Java", "Hard"),
            ]
        )

        matched = get_matched_skills(persona, job, "Hard")

        assert "Python" in matched
        assert "SQL" not in matched  # Not in job
        assert "Leadership" not in matched  # Wrong type

    def test_returns_empty_list_when_no_matches(self) -> None:
        """Returns empty list when no skills match."""
        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(extracted_skills=[MockExtractedSkill("Java", "Hard")])

        matched = get_matched_skills(persona, job, "Hard")

        assert matched == []


class TestGetMissingSkills:
    """Tests for get_missing_skills helper."""

    def test_returns_missing_required_skills(self) -> None:
        """Returns required skills that persona lacks."""
        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Python", "Hard", is_required=True),
                MockExtractedSkill("Kubernetes", "Hard", is_required=True),
                MockExtractedSkill("Nice-to-have", "Hard", is_required=False),
            ]
        )

        missing = get_missing_skills(persona, job, "Hard", required_only=True)

        assert "Kubernetes" in missing
        assert "Python" not in missing  # Persona has it
        assert "Nice-to-have" not in missing  # Not required

    def test_returns_all_missing_when_not_required_only(self) -> None:
        """Returns all missing skills when required_only is False."""
        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Kubernetes", "Hard", is_required=True),
                MockExtractedSkill("Nice-to-have", "Hard", is_required=False),
            ]
        )

        missing = get_missing_skills(persona, job, "Hard", required_only=False)

        assert "Kubernetes" in missing
        assert "Nice-to-have" in missing


class TestGetTargetSkillMatches:
    """Tests for get_target_skill_matches helper."""

    def test_returns_target_skills_in_job(self) -> None:
        """Returns target skills that appear in job requirements."""
        persona = MockPersona(target_skills=["Machine Learning", "Kubernetes", "AWS"])
        job = MockJobPosting(
            extracted_skills=[
                MockExtractedSkill("Machine Learning", "Hard"),
                MockExtractedSkill("Python", "Hard"),
            ]
        )

        matches = get_target_skill_matches(persona, job)

        assert "Machine Learning" in matches
        assert "Kubernetes" not in matches  # Not in job
        assert "AWS" not in matches  # Not in job


class TestGenerateSummarySentence:
    """Tests for generate_summary_sentence helper."""

    def test_generates_summary_for_strong_fit(self) -> None:
        """Generates positive summary for high scores."""
        summary = generate_summary_sentence(
            fit_total=85,
            _stretch_total=60,
            strengths=["Strong technical fit"],
            gaps=[],
        )

        assert len(summary) > 0
        assert "strong" in summary.lower() or "good" in summary.lower()

    def test_generates_summary_acknowledging_gaps(self) -> None:
        """Summary acknowledges gaps when present."""
        summary = generate_summary_sentence(
            fit_total=60,
            _stretch_total=50,
            strengths=["Some experience"],
            gaps=["Missing required skill: Kubernetes"],
        )

        assert len(summary) > 0
        # Summary should acknowledge the gaps exist
        assert (
            "gap" in summary.lower()
            or "missing" in summary.lower()
            or "may need" in summary.lower()
        )


# =============================================================================
# Edge Case Tests (REQ-008 §8.2)
# =============================================================================


class TestEmptyLists:
    """Tests for empty input list handling."""

    def test_empty_persona_skills(self) -> None:
        """Explanation works when persona has no skills."""
        fit_result = make_fit_result(hard_skills=85.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(skills=[])
        job = MockJobPosting(extracted_skills=[MockExtractedSkill("Python", "Hard")])

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should still generate explanation without crash
        assert isinstance(explanation, ScoreExplanation)
        # High hard skills score but no matches should produce generic message
        assert len(explanation.strengths) >= 1

    def test_empty_job_extracted_skills(self) -> None:
        """Explanation works when job has no extracted skills."""
        fit_result = make_fit_result(hard_skills=40.0)
        stretch_result = make_stretch_result()

        persona = MockPersona(skills=[MockSkill("Python", "Hard")])
        job = MockJobPosting(extracted_skills=[])

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should still generate explanation without crash
        assert isinstance(explanation, ScoreExplanation)

    def test_empty_target_skills(self) -> None:
        """Explanation works when persona has no target skills."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result(target_skills=80.0)

        persona = MockPersona(target_skills=[])
        job = MockJobPosting(extracted_skills=[MockExtractedSkill("Python", "Hard")])

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should still generate explanation
        assert isinstance(explanation, ScoreExplanation)

    def test_empty_target_roles(self) -> None:
        """Explanation works when persona has no target roles."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result(target_role=85.0)

        persona = MockPersona(target_roles=[])
        job = MockJobPosting()

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # Should still generate explanation with generic message
        assert isinstance(explanation, ScoreExplanation)
        assert len(explanation.stretch_opportunities) >= 1


class TestNeutralScores:
    """Tests for neutral/middle scores."""

    def test_all_neutral_scores_minimal_output(self) -> None:
        """Neutral scores produce minimal explanation content."""
        # All components at neutral values
        fit_result = make_fit_result(
            hard_skills=70.0,
            soft_skills=70.0,
            experience_level=70.0,
            role_title=70.0,
            location_logistics=70.0,
        )
        stretch_result = make_stretch_result(
            target_role=50.0,
            target_skills=50.0,
            growth_trajectory=50.0,
        )

        persona = MockPersona()
        job = MockJobPosting()

        explanation = generate_explanation(fit_result, stretch_result, persona, job)

        # With neutral scores, should have minimal strengths/gaps/stretch
        # (only warnings for undisclosed salary if applicable)
        assert isinstance(explanation, ScoreExplanation)
        assert explanation.summary is not None


class TestInputSizeValidation:
    """Tests for input size limits."""

    def test_rejects_oversized_persona_skills(self) -> None:
        """Raises ValueError when persona has too many skills."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        # Create persona with > 500 skills
        oversized_skills = [MockSkill(f"Skill{i}", "Hard") for i in range(501)]
        persona = MockPersona(skills=oversized_skills)
        job = MockJobPosting()

        with pytest.raises(ValueError, match="Persona skills exceed maximum"):
            generate_explanation(fit_result, stretch_result, persona, job)

    def test_rejects_oversized_job_skills(self) -> None:
        """Raises ValueError when job has too many extracted skills."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        persona = MockPersona()
        # Create job with > 500 skills
        oversized_skills = [MockExtractedSkill(f"Skill{i}", "Hard") for i in range(501)]
        job = MockJobPosting(extracted_skills=oversized_skills)

        with pytest.raises(ValueError, match="Job extracted skills exceed maximum"):
            generate_explanation(fit_result, stretch_result, persona, job)

    def test_rejects_oversized_target_skills(self) -> None:
        """Raises ValueError when persona has too many target skills."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        # Create persona with > 500 target skills
        oversized_targets = [f"TargetSkill{i}" for i in range(501)]
        persona = MockPersona(target_skills=oversized_targets)
        job = MockJobPosting()

        with pytest.raises(ValueError, match="Persona target skills exceed maximum"):
            generate_explanation(fit_result, stretch_result, persona, job)

    def test_accepts_max_size_skills(self) -> None:
        """Accepts exactly 500 skills (boundary test)."""
        fit_result = make_fit_result()
        stretch_result = make_stretch_result()

        # Create persona with exactly 500 skills
        max_skills = [MockSkill(f"Skill{i}", "Hard") for i in range(500)]
        persona = MockPersona(skills=max_skills)
        job = MockJobPosting()

        # Should not raise
        explanation = generate_explanation(fit_result, stretch_result, persona, job)
        assert isinstance(explanation, ScoreExplanation)
