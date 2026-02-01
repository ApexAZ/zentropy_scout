"""Unit tests for soft skills match calculation.

REQ-008 §4.3: Soft Skills Match component (15% of Fit Score).

Tests cover:
- Cosine similarity calculation
- Embedding-based soft skills matching
- Edge cases (missing data, zero vectors)
"""

import pytest

from app.services.soft_skills_match import (
    calculate_soft_skills_score,
    cosine_similarity,
)

# =============================================================================
# Cosine Similarity Tests
# =============================================================================


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_identical_vectors_returns_one(self) -> None:
        """Identical normalized vectors have similarity 1.0."""
        vec = [0.6, 0.8, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_vectors_returns_zero(self) -> None:
        """Perpendicular vectors have similarity 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(0.0, abs=0.001)

    def test_opposite_vectors_returns_negative_one(self) -> None:
        """Opposite vectors have similarity -1.0."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        assert cosine_similarity(vec1, vec2) == pytest.approx(-1.0, abs=0.001)

    def test_similar_vectors_positive_correlation(self) -> None:
        """Similar vectors have positive correlation."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [1.1, 2.1, 2.9]
        sim = cosine_similarity(vec1, vec2)
        assert sim > 0.9  # Very similar

    def test_zero_vector_returns_zero(self) -> None:
        """Zero vector has similarity 0 with any vector."""
        vec1 = [1.0, 2.0, 3.0]
        zero = [0.0, 0.0, 0.0]
        assert cosine_similarity(vec1, zero) == 0.0
        assert cosine_similarity(zero, vec1) == 0.0

    def test_both_zero_vectors_returns_zero(self) -> None:
        """Two zero vectors have similarity 0."""
        zero = [0.0, 0.0, 0.0]
        assert cosine_similarity(zero, zero) == 0.0

    def test_mismatched_lengths_raises_error(self) -> None:
        """Vectors of different lengths raise ValueError."""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="same length"):
            cosine_similarity(vec1, vec2)

    def test_high_dimensional_vectors(self) -> None:
        """Works with high-dimensional vectors (1536 dimensions)."""
        # Simulate OpenAI embedding dimensions
        vec1 = [0.01 * i for i in range(1536)]
        vec2 = [0.01 * (i + 0.5) for i in range(1536)]
        sim = cosine_similarity(vec1, vec2)
        assert -1.0 <= sim <= 1.0

    def test_empty_vectors_raises_error(self) -> None:
        """Empty vectors raise ValueError."""
        with pytest.raises(ValueError, match="same length|empty"):
            cosine_similarity([], [])

    def test_nan_in_vector_raises_error(self) -> None:
        """NaN values in vectors raise ValueError."""
        vec_with_nan = [1.0, float("nan"), 3.0]
        normal_vec = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="finite"):
            cosine_similarity(vec_with_nan, normal_vec)
        with pytest.raises(ValueError, match="finite"):
            cosine_similarity(normal_vec, vec_with_nan)

    def test_inf_in_vector_raises_error(self) -> None:
        """Infinity values in vectors raise ValueError."""
        vec_with_inf = [1.0, float("inf"), 3.0]
        normal_vec = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="finite"):
            cosine_similarity(vec_with_inf, normal_vec)
        # Also test negative infinity
        vec_with_neg_inf = [1.0, float("-inf"), 3.0]
        with pytest.raises(ValueError, match="finite"):
            cosine_similarity(vec_with_neg_inf, normal_vec)


# =============================================================================
# Soft Skills Score Calculation Tests (REQ-008 §4.3)
# =============================================================================


class TestCalculateSoftSkillsScore:
    """Tests for the main soft skills score calculation."""

    def test_no_job_embedding_returns_neutral(self) -> None:
        """No job soft skills returns neutral score (70)."""
        persona_embedding = [0.5, 0.5, 0.5]
        # None indicates no job soft skills extracted
        score = calculate_soft_skills_score(persona_embedding, None)
        assert score == 70.0

    def test_no_persona_embedding_returns_neutral(self) -> None:
        """No persona soft skills returns neutral score (70)."""
        job_embedding = [0.5, 0.5, 0.5]
        score = calculate_soft_skills_score(None, job_embedding)
        assert score == 70.0

    def test_both_none_returns_neutral(self) -> None:
        """Both embeddings missing returns neutral score."""
        score = calculate_soft_skills_score(None, None)
        assert score == 70.0

    def test_identical_embeddings_returns_100(self) -> None:
        """Identical embeddings (perfect match) return 100."""
        embedding = [0.6, 0.8, 0.0]
        score = calculate_soft_skills_score(embedding, embedding)
        assert score == pytest.approx(100.0, abs=0.1)

    def test_opposite_embeddings_returns_zero(self) -> None:
        """Opposite embeddings return 0."""
        persona = [1.0, 0.0]
        job = [-1.0, 0.0]
        score = calculate_soft_skills_score(persona, job)
        assert score == pytest.approx(0.0, abs=0.1)

    def test_orthogonal_embeddings_returns_50(self) -> None:
        """Orthogonal embeddings (no correlation) return 50."""
        persona = [1.0, 0.0, 0.0]
        job = [0.0, 1.0, 0.0]
        score = calculate_soft_skills_score(persona, job)
        assert score == pytest.approx(50.0, abs=0.1)

    def test_similar_embeddings_high_score(self) -> None:
        """Similar embeddings return high score (>75)."""
        persona = [1.0, 2.0, 3.0]
        job = [1.1, 2.1, 2.9]
        score = calculate_soft_skills_score(persona, job)
        assert score > 75.0

    def test_scaling_formula(self) -> None:
        """Verify scaling: score = (cosine + 1) * 50."""
        # Known cosine similarity: vec1 . vec2 / (||vec1|| * ||vec2||)
        # vec1 = [3, 4] -> ||vec1|| = 5
        # vec2 = [4, 3] -> ||vec2|| = 5
        # dot = 12 + 12 = 24
        # cosine = 24 / 25 = 0.96
        # score = (0.96 + 1) * 50 = 98
        persona = [3.0, 4.0]
        job = [4.0, 3.0]
        expected_cosine = 24.0 / 25.0
        expected_score = (expected_cosine + 1) * 50
        score = calculate_soft_skills_score(persona, job)
        assert score == pytest.approx(expected_score, abs=0.1)

    def test_zero_persona_embedding_returns_50(self) -> None:
        """Zero persona embedding (neutral) returns 50 (not neutral 70).

        Note: Zero vector has cosine=0 with any vector.
        Score = (0 + 1) * 50 = 50.
        This differs from "no embedding" which returns 70.
        """
        persona = [0.0, 0.0, 0.0]
        job = [1.0, 2.0, 3.0]
        score = calculate_soft_skills_score(persona, job)
        assert score == pytest.approx(50.0, abs=0.1)

    def test_high_dimensional_embeddings(self) -> None:
        """Works with high-dimensional embeddings (1536)."""
        # Simulate OpenAI embedding dimensions
        persona = [0.01 * i for i in range(1536)]
        job = [0.01 * (i + 0.5) for i in range(1536)]
        score = calculate_soft_skills_score(persona, job)
        assert 0 <= score <= 100

    def test_mismatched_dimensions_raises_error(self) -> None:
        """Embeddings with different dimensions raise ValueError."""
        persona = [1.0, 2.0]
        job = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="same length|dimension"):
            calculate_soft_skills_score(persona, job)

    def test_empty_embeddings_raises_error(self) -> None:
        """Empty embedding lists raise ValueError."""
        with pytest.raises(ValueError, match="empty|same length"):
            calculate_soft_skills_score([], [])

    def test_worked_example_from_spec(self) -> None:
        """Verify worked example from REQ-008 §4.3.

        Persona soft skills: "Communication", "Team Leadership", "Problem-solving"
        Job soft skills: "Communication", "Collaboration", "Analytical thinking"

        Assume cosine similarity = 0.6 (good semantic overlap)
        Score = (0.6 + 1) * 50 = 80
        """
        # Create mock embeddings that produce cosine ~0.6
        # We use known vectors where we can control the similarity
        # For cosine = 0.6, we need dot(a,b) = 0.6 * ||a|| * ||b||
        # Use unit vectors for simplicity
        # a = [0.8, 0.6], ||a|| = 1
        # b = [0.6, 0.8], ||b|| = 1
        # dot = 0.48 + 0.48 = 0.96 (too high)

        # Let's use: a = [1, 0], b = [0.6, 0.8]
        # dot = 0.6, ||a|| = 1, ||b|| = 1
        # cosine = 0.6
        persona = [1.0, 0.0]
        job = [0.6, 0.8]  # Unit vector at angle arccos(0.6) from [1,0]
        score = calculate_soft_skills_score(persona, job)
        assert score == pytest.approx(80.0, abs=0.1)

    def test_rejects_oversized_embeddings(self) -> None:
        """Raises ValueError if embedding exceeds max dimensions."""
        # Reasonable max is ~3000 (2x OpenAI dimensions)
        oversized = [0.1] * 5001
        normal = [0.1] * 5001
        with pytest.raises(ValueError, match="exceed maximum"):
            calculate_soft_skills_score(oversized, normal)
