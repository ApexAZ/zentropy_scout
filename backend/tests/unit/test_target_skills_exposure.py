"""Unit tests for Target Skills Exposure calculation.

REQ-008 §5.3: Target Skills Exposure component (40% of Stretch Score).

Tests cover:
- Missing target skills returns neutral score
- Tiered scoring based on match count (0→20, 1→50, 2→75, 3+→100)
- Skill normalization (case, synonyms)
- Edge cases (empty lists, max sizes)
"""

import pytest

from app.services.stretch_score import (
    STRETCH_NEUTRAL_SCORE,
    calculate_target_skills_exposure,
)

# =============================================================================
# Missing Target Skills (REQ-008 §5.3)
# =============================================================================


class TestMissingTargetSkills:
    """Tests for neutral score when target skills not defined."""

    def test_no_target_skills_returns_neutral(self) -> None:
        """No target skills returns neutral score (50)."""
        score = calculate_target_skills_exposure(
            target_skills=None,
            job_skills=["Python", "JavaScript"],
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_empty_target_skills_list_returns_neutral(self) -> None:
        """Empty target skills list returns neutral score."""
        score = calculate_target_skills_exposure(
            target_skills=[],
            job_skills=["Python", "JavaScript"],
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_whitespace_only_target_skills_returns_neutral(self) -> None:
        """Target skills with only whitespace are treated as empty."""
        score = calculate_target_skills_exposure(
            target_skills=["   ", "\t", "\n"],
            job_skills=["Python", "JavaScript"],
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_no_job_skills_returns_zero_matches(self) -> None:
        """No job skills means 0 matches → score 20."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform"],
            job_skills=None,
        )
        assert score == 20.0

    def test_empty_job_skills_list_returns_zero_matches(self) -> None:
        """Empty job skills list means 0 matches → score 20."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform"],
            job_skills=[],
        )
        assert score == 20.0

    def test_whitespace_only_job_skills_returns_zero_matches(self) -> None:
        """Job skills with only whitespace count as 0 matches → 20."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform"],
            job_skills=["   ", "\t", "\n"],
        )
        assert score == 20.0

    def test_mixed_valid_and_whitespace_target_skills(self) -> None:
        """Valid skills mixed with whitespace filter out whitespace."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "   ", "Terraform"],
            job_skills=["Kubernetes", "Terraform"],
        )
        assert score == 75.0  # 2 matches


# =============================================================================
# Tiered Scoring (REQ-008 §5.3)
# =============================================================================


class TestTieredScoring:
    """Tests for match count to score mapping."""

    def test_zero_matches_returns_20(self) -> None:
        """No matches = job has no target skill exposure → 20."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform"],
            job_skills=["Python", "JavaScript", "React"],
        )
        assert score == 20.0

    def test_one_match_returns_50(self) -> None:
        """1 match → 50."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform", "Go"],
            job_skills=["Python", "Kubernetes", "React"],
        )
        assert score == 50.0

    def test_two_matches_returns_75(self) -> None:
        """2 matches → 75."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform", "Go"],
            job_skills=["Python", "Kubernetes", "Terraform"],
        )
        assert score == 75.0

    def test_three_matches_returns_100(self) -> None:
        """3 matches → 100."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform", "Go"],
            job_skills=["Kubernetes", "Terraform", "Go", "Python"],
        )
        assert score == 100.0

    def test_four_or_more_matches_returns_100(self) -> None:
        """4+ matches still returns 100 (ceiling)."""
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform", "Go", "Rust", "Zig"],
            job_skills=["Kubernetes", "Terraform", "Go", "Rust", "Zig", "Python"],
        )
        assert score == 100.0


# =============================================================================
# Skill Normalization (REQ-008 §5.3)
# =============================================================================


class TestSkillNormalization:
    """Tests for skill normalization in matching."""

    def test_case_insensitive_matching(self) -> None:
        """Matching is case-insensitive."""
        score = calculate_target_skills_exposure(
            target_skills=["KUBERNETES", "terraform"],
            job_skills=["kubernetes", "TERRAFORM"],
        )
        assert score == 75.0

    def test_synonym_matching(self) -> None:
        """Synonyms are resolved before matching (k8s → kubernetes)."""
        score = calculate_target_skills_exposure(
            target_skills=["k8s", "Terraform"],
            job_skills=["Kubernetes", "Terraform"],
        )
        assert score == 75.0

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace is stripped."""
        score = calculate_target_skills_exposure(
            target_skills=["  Kubernetes  ", "Terraform"],
            job_skills=["Kubernetes", "  Terraform  "],
        )
        assert score == 75.0


# =============================================================================
# Input Validation
# =============================================================================


class TestInputValidation:
    """Tests for input validation and error handling."""

    def test_too_many_target_skills_raises_error(self) -> None:
        """Too many target skills raises ValueError."""
        too_many = [f"Skill{i}" for i in range(501)]
        with pytest.raises(ValueError, match="maximum"):
            calculate_target_skills_exposure(
                target_skills=too_many,
                job_skills=["Python"],
            )

    def test_too_many_job_skills_raises_error(self) -> None:
        """Too many job skills raises ValueError."""
        too_many = [f"Skill{i}" for i in range(501)]
        with pytest.raises(ValueError, match="maximum"):
            calculate_target_skills_exposure(
                target_skills=["Python"],
                job_skills=too_many,
            )

    def test_exactly_max_target_skills_succeeds(self) -> None:
        """Exactly 500 target skills does not raise."""
        exactly_max = [f"Skill{i}" for i in range(500)]
        score = calculate_target_skills_exposure(
            target_skills=exactly_max,
            job_skills=["Skill0"],
        )
        assert score == 50.0  # 1 match


# =============================================================================
# Worked Examples from Spec
# =============================================================================


class TestWorkedExamples:
    """Tests verifying worked examples from REQ-008 §5.3."""

    def test_user_targets_kubernetes_terraform_go(self) -> None:
        """User targets Kubernetes, Terraform, Go.

        Job requires Python, Kubernetes, Docker, Terraform.
        Intersection: {kubernetes, terraform} = 2 matches.
        Expected: 75
        """
        score = calculate_target_skills_exposure(
            target_skills=["Kubernetes", "Terraform", "Go"],
            job_skills=["Python", "Kubernetes", "Docker", "Terraform"],
        )
        assert score == 75.0

    def test_no_targets_defined(self) -> None:
        """User has no growth targets defined.

        Expected: 50 (neutral score).
        """
        score = calculate_target_skills_exposure(
            target_skills=None,
            job_skills=["Python", "React", "TypeScript"],
        )
        assert score == 50.0

    def test_job_has_none_of_target_skills(self) -> None:
        """User targets ML skills, job is frontend.

        No exposure to target skills.
        Expected: 20
        """
        score = calculate_target_skills_exposure(
            target_skills=["TensorFlow", "PyTorch", "MLOps"],
            job_skills=["React", "TypeScript", "CSS", "HTML"],
        )
        assert score == 20.0
