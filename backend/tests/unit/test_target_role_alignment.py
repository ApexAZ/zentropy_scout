"""Unit tests for Target Role Alignment calculation.

REQ-008 §5.2: Target Role Alignment component (50% of Stretch Score).

Tests cover:
- Exact match detection (after title normalization)
- Semantic similarity scoring with baseline
- Missing target roles returns neutral score
- Edge cases (empty lists, dimension mismatches)
"""

import pytest

from app.services.stretch_score import (
    STRETCH_NEUTRAL_SCORE,
    calculate_target_role_alignment,
)

# =============================================================================
# Missing Target Roles (REQ-008 §5.2)
# =============================================================================


class TestMissingTargetRoles:
    """Tests for neutral score when target roles not defined."""

    def test_no_target_roles_returns_neutral(self) -> None:
        """No target roles returns neutral score (50)."""
        score = calculate_target_role_alignment(
            target_roles=None,
            job_title="Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_empty_target_roles_list_returns_neutral(self) -> None:
        """Empty target roles list returns neutral score."""
        score = calculate_target_role_alignment(
            target_roles=[],
            job_title="Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_whitespace_only_target_roles_returns_neutral(self) -> None:
        """Target roles with only whitespace are treated as empty."""
        score = calculate_target_role_alignment(
            target_roles=["   ", "\t", "\n"],
            job_title="Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_no_job_title_returns_neutral(self) -> None:
        """No job title returns neutral score."""
        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],
            job_title=None,
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE

    def test_empty_job_title_returns_neutral(self) -> None:
        """Empty job title returns neutral score."""
        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],
            job_title="",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE


# =============================================================================
# Exact Match (REQ-008 §5.2)
# =============================================================================


class TestExactMatch:
    """Tests for exact match detection after normalization."""

    def test_exact_match_returns_100(self) -> None:
        """Exact match (case-insensitive) returns 100."""
        score = calculate_target_role_alignment(
            target_roles=["Software Engineer"],
            job_title="software engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_with_seniority_normalization(self) -> None:
        """Exact match after seniority normalization (Sr. -> senior)."""
        score = calculate_target_role_alignment(
            target_roles=["Senior Software Engineer"],
            job_title="Sr. Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_with_synonym_normalization(self) -> None:
        """Exact match after role synonym normalization."""
        score = calculate_target_role_alignment(
            target_roles=["Software Engineer"],
            job_title="SWE",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_any_target_role(self) -> None:
        """Any target role matching returns 100."""
        score = calculate_target_role_alignment(
            target_roles=["Product Manager", "Software Engineer", "Data Scientist"],
            job_title="Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_no_exact_match_falls_through_to_semantic(self) -> None:
        """No exact match falls through to semantic similarity."""
        # Without embeddings, returns neutral
        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],
            job_title="Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == STRETCH_NEUTRAL_SCORE


# =============================================================================
# Semantic Similarity (REQ-008 §5.2)
# =============================================================================


class TestSemanticSimilarity:
    """Tests for embedding-based semantic similarity scoring."""

    def test_semantic_formula_perfect_similarity(self) -> None:
        """Perfect similarity (1.0) returns 100.

        Formula: max(0, 30 + (similarity + 1) * 35)
        1.0 -> 30 + (1 + 1) * 35 = 30 + 70 = 100
        """
        # Identical vectors have cosine similarity of 1.0
        embedding = [0.6, 0.8, 0.0]
        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],  # No exact match
            job_title="Engineering Manager",
            target_roles_embedding=embedding,
            job_title_embedding=embedding,
        )
        assert score == pytest.approx(100.0, abs=0.1)

    def test_semantic_formula_zero_similarity(self) -> None:
        """Zero similarity (orthogonal vectors) returns 65.

        Formula: max(0, 30 + (similarity + 1) * 35)
        0.0 -> 30 + (0 + 1) * 35 = 30 + 35 = 65
        """
        # Orthogonal vectors have cosine similarity of 0.0
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],
            job_title="Software Engineer",
            target_roles_embedding=vec1,
            job_title_embedding=vec2,
        )
        assert score == pytest.approx(65.0, abs=0.1)

    def test_semantic_formula_negative_similarity(self) -> None:
        """Negative similarity (-1.0, opposite vectors) returns 30.

        Formula: max(0, 30 + (similarity + 1) * 35)
        -1.0 -> 30 + (-1 + 1) * 35 = 30 + 0 = 30

        Note: Unlike Role Title Match (0-100), Target Role Alignment
        has a 30-point baseline because growth roles should be somewhat related.
        """
        # Opposite vectors have cosine similarity of -1.0
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],
            job_title="Software Engineer",
            target_roles_embedding=vec1,
            job_title_embedding=vec2,
        )
        assert score == pytest.approx(30.0, abs=0.1)

    def test_semantic_high_similarity_high_score(self) -> None:
        """High similarity embeddings produce score > 75."""
        # Similar vectors
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.1, 2.1, 2.9]
        score = calculate_target_role_alignment(
            target_roles=["Data Analyst"],
            job_title="Business Analyst",
            target_roles_embedding=vec1,
            job_title_embedding=vec2,
        )
        assert score > 75.0

    def test_semantic_with_high_dimensional_embeddings(self) -> None:
        """Works with high-dimensional embeddings (1536 dimensions)."""
        # Simulate OpenAI text-embedding-3-small dimensions
        vec1 = [0.01 * i for i in range(1536)]
        vec2 = [0.01 * (i + 0.5) for i in range(1536)]
        score = calculate_target_role_alignment(
            target_roles=["Senior Engineer"],
            job_title="Staff Engineer",
            target_roles_embedding=vec1,
            job_title_embedding=vec2,
        )
        assert 30 <= score <= 100


# =============================================================================
# Input Validation
# =============================================================================


class TestInputValidation:
    """Tests for input validation and error handling."""

    def test_mismatched_embedding_dimensions_raises_error(self) -> None:
        """Embeddings with different dimensions raise ValueError."""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="dimensions must match"):
            calculate_target_role_alignment(
                target_roles=["Product Manager"],
                job_title="Software Engineer",
                target_roles_embedding=vec1,
                job_title_embedding=vec2,
            )

    def test_empty_embedding_raises_error(self) -> None:
        """Empty embeddings raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            calculate_target_role_alignment(
                target_roles=["Product Manager"],
                job_title="Software Engineer",
                target_roles_embedding=[],
                job_title_embedding=[],
            )

    def test_oversized_embedding_raises_error(self) -> None:
        """Embeddings exceeding max dimensions raise ValueError."""
        oversized = [0.1] * 5001
        with pytest.raises(ValueError, match="exceed maximum"):
            calculate_target_role_alignment(
                target_roles=["Product Manager"],
                job_title="Software Engineer",
                target_roles_embedding=oversized,
                job_title_embedding=oversized,
            )

    def test_too_many_target_roles_raises_error(self) -> None:
        """Too many target roles raises ValueError."""
        too_many = [f"Role {i}" for i in range(101)]
        with pytest.raises(ValueError, match="maximum"):
            calculate_target_role_alignment(
                target_roles=too_many,
                job_title="Software Engineer",
                target_roles_embedding=None,
                job_title_embedding=None,
            )


# =============================================================================
# Worked Examples from Spec
# =============================================================================


class TestWorkedExamples:
    """Tests verifying worked examples from REQ-008 §5.2."""

    def test_exact_match_scenario(self) -> None:
        """User targets 'Product Manager', job is 'Product Manager'.

        Expected: 100 (exact match after normalization).
        """
        score = calculate_target_role_alignment(
            target_roles=["Product Manager", "Engineering Manager"],
            job_title="product manager",  # Lowercase, still exact match
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_semantic_match_scenario(self) -> None:
        """User targets 'Product Manager', job is 'Program Manager'.

        Expected: High score due to semantic similarity, but not 100.
        Using cosine similarity of ~0.8 (realistic for related titles):
        score = 30 + (0.8 + 1) * 35 = 30 + 63 = 93
        """
        # Create embeddings that produce cosine similarity ~0.8
        # Use unit vectors at angle arccos(0.8) apart
        vec1 = [1.0, 0.0]  # Unit vector along x-axis
        vec2 = [0.8, 0.6]  # Unit vector at ~37 degrees (cosine = 0.8)

        score = calculate_target_role_alignment(
            target_roles=["Product Manager"],
            job_title="Program Manager",
            target_roles_embedding=vec1,
            job_title_embedding=vec2,
        )
        # 30 + (0.8 + 1) * 35 = 30 + 63 = 93
        assert score == pytest.approx(93.0, abs=0.1)

    def test_no_growth_targets_scenario(self) -> None:
        """User has no growth targets defined.

        Expected: 50 (neutral score).
        """
        score = calculate_target_role_alignment(
            target_roles=None,
            job_title="Software Engineer",
            target_roles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 50.0
