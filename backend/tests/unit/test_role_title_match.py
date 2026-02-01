"""Unit tests for role title match calculation.

REQ-008 §4.5: Role Title Match component (10% of Fit Score).

Tests cover:
- Title normalization (synonyms, case, whitespace)
- Exact match detection (returns 100)
- Semantic similarity calculation
- Edge cases (missing data, empty inputs)
"""

import pytest

from app.services.role_title_match import (
    calculate_role_title_score,
    normalize_title,
)

# =============================================================================
# Title Normalization Tests (REQ-008 §4.5.2)
# =============================================================================


class TestNormalizeTitle:
    """Tests for title normalization function."""

    def test_lowercase_conversion(self) -> None:
        """Converts title to lowercase."""
        assert normalize_title("Software Engineer") == "software engineer"

    def test_whitespace_stripping(self) -> None:
        """Strips leading and trailing whitespace."""
        assert normalize_title("  Software Engineer  ") == "software engineer"

    def test_multiple_spaces_normalized(self) -> None:
        """Multiple internal spaces reduced to single space."""
        assert normalize_title("Software   Engineer") == "software engineer"

    # --- Seniority prefix normalization ---

    def test_sr_prefix_normalized(self) -> None:
        """'Sr.' prefix normalized to 'senior'."""
        assert normalize_title("Sr. Software Engineer") == "senior software engineer"

    def test_senior_prefix_preserved(self) -> None:
        """'Senior' prefix preserved as-is (already standard)."""
        assert normalize_title("Senior Software Engineer") == "senior software engineer"

    def test_lead_prefix_to_senior(self) -> None:
        """'Lead' prefix normalized to 'senior'."""
        assert normalize_title("Lead Software Engineer") == "senior software engineer"

    def test_principal_prefix_to_senior(self) -> None:
        """'Principal' prefix normalized to 'senior'."""
        assert normalize_title("Principal Engineer") == "senior engineer"

    def test_jr_prefix_normalized(self) -> None:
        """'Jr.' prefix normalized to 'junior'."""
        assert normalize_title("Jr. Developer") == "junior developer"

    def test_junior_prefix_preserved(self) -> None:
        """'Junior' prefix preserved as-is (already standard)."""
        assert normalize_title("Junior Developer") == "junior developer"

    def test_associate_prefix_to_junior(self) -> None:
        """'Associate' prefix normalized to 'junior'."""
        assert (
            normalize_title("Associate Software Engineer") == "junior software engineer"
        )

    # --- Role synonym normalization ---

    def test_software_developer_to_software_engineer(self) -> None:
        """'Software Developer' normalized to 'Software Engineer'."""
        assert normalize_title("Software Developer") == "software engineer"

    def test_sde_to_software_engineer(self) -> None:
        """'SDE' normalized to 'Software Engineer'."""
        assert normalize_title("SDE") == "software engineer"

    def test_swe_to_software_engineer(self) -> None:
        """'SWE' normalized to 'Software Engineer'."""
        assert normalize_title("SWE") == "software engineer"

    def test_pm_to_product_manager(self) -> None:
        """'PM' normalized to 'Product Manager'."""
        assert normalize_title("PM") == "product manager"

    def test_product_manager_preserved(self) -> None:
        """'Product Manager' preserved as-is."""
        assert normalize_title("Product Manager") == "product manager"

    def test_devops_engineer_normalized(self) -> None:
        """'DevOps Engineer' normalized (case preserved in canonical form)."""
        assert normalize_title("DevOps Engineer") == "devops engineer"

    def test_unknown_title_passthrough(self) -> None:
        """Unknown titles pass through with only case/whitespace changes."""
        assert normalize_title("Chief Happiness Officer") == "chief happiness officer"

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert normalize_title("") == ""

    def test_combined_normalization(self) -> None:
        """Combined prefix and role normalization."""
        assert normalize_title("Sr. Software Developer") == "senior software engineer"
        assert normalize_title("Jr. SDE") == "junior software engineer"

    def test_oversized_title_truncated(self) -> None:
        """Titles exceeding max length are truncated."""
        oversized = "A" * 600  # Exceeds _MAX_TITLE_LENGTH (500)
        result = normalize_title(oversized)
        # Truncated to 500 chars, then lowercased
        assert len(result) == 500
        assert result == "a" * 500


# =============================================================================
# Exact Match Tests (REQ-008 §4.5.1)
# =============================================================================


class TestExactMatch:
    """Tests for exact title match (returns 100)."""

    def test_exact_match_current_role(self) -> None:
        """Current role exact match returns 100."""
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=[],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_case_insensitive(self) -> None:
        """Exact match is case insensitive."""
        score = calculate_role_title_score(
            current_role="SOFTWARE ENGINEER",
            work_history_titles=[],
            job_title="software engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_with_normalization(self) -> None:
        """Exact match works after normalization."""
        score = calculate_role_title_score(
            current_role="Sr. Software Developer",
            work_history_titles=[],
            job_title="Senior Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_in_work_history(self) -> None:
        """Match found in work history returns 100."""
        score = calculate_role_title_score(
            current_role="Team Lead",
            work_history_titles=["Software Engineer", "Junior Developer"],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_exact_match_via_synonym(self) -> None:
        """Match via synonym normalization returns 100."""
        score = calculate_role_title_score(
            current_role="SDE",
            work_history_titles=[],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0


# =============================================================================
# Semantic Similarity Tests (REQ-008 §4.5.3)
# =============================================================================


class TestSemanticSimilarity:
    """Tests for embedding-based semantic similarity."""

    def test_high_similarity_high_score(self) -> None:
        """High cosine similarity yields high score."""
        # Embeddings with cosine similarity ~0.8
        # cos = 0.8, score = (0.8 + 1) * 50 = 90
        user_emb = [0.8, 0.6]  # ||v|| = 1
        job_emb = [0.6, 0.8]  # ||v|| = 1, dot = 0.96
        score = calculate_role_title_score(
            current_role="Marketing Manager",
            work_history_titles=[],
            job_title="Sales Director",
            user_titles_embedding=user_emb,
            job_title_embedding=job_emb,
        )
        # cos = 0.96, score = (0.96 + 1) * 50 = 98
        assert score == pytest.approx(98.0, abs=0.1)

    def test_orthogonal_embeddings_returns_50(self) -> None:
        """Orthogonal embeddings (no correlation) return 50."""
        user_emb = [1.0, 0.0, 0.0]
        job_emb = [0.0, 1.0, 0.0]
        score = calculate_role_title_score(
            current_role="Plumber",
            work_history_titles=[],
            job_title="Astronaut",
            user_titles_embedding=user_emb,
            job_title_embedding=job_emb,
        )
        assert score == pytest.approx(50.0, abs=0.1)

    def test_low_similarity_low_score(self) -> None:
        """Low/negative cosine similarity yields low score."""
        # Opposite embeddings: cos = -1, score = 0
        user_emb = [1.0, 0.0]
        job_emb = [-1.0, 0.0]
        score = calculate_role_title_score(
            current_role="Chef",
            work_history_titles=[],
            job_title="Accountant",
            user_titles_embedding=user_emb,
            job_title_embedding=job_emb,
        )
        assert score == pytest.approx(0.0, abs=0.1)

    def test_identical_embeddings_returns_100(self) -> None:
        """Identical embeddings (but no exact title match) return 100."""
        emb = [0.5, 0.5, 0.5, 0.5]
        score = calculate_role_title_score(
            current_role="Data Analyst",
            work_history_titles=["Business Analyst"],
            job_title="Data Scientist",
            user_titles_embedding=emb,
            job_title_embedding=emb,
        )
        assert score == pytest.approx(100.0, abs=0.1)

    def test_known_similarity_formula(self) -> None:
        """Verify score = (cosine + 1) * 50 formula."""
        # For cosine = 0.6: score = (0.6 + 1) * 50 = 80
        # Construct vectors with known cosine similarity
        user_emb = [1.0, 0.0]
        job_emb = [0.6, 0.8]  # Unit vector at arccos(0.6) from [1, 0]
        score = calculate_role_title_score(
            current_role="Developer",
            work_history_titles=[],
            job_title="Engineer",
            user_titles_embedding=user_emb,
            job_title_embedding=job_emb,
        )
        assert score == pytest.approx(80.0, abs=0.1)


# =============================================================================
# Missing Data Tests (REQ-008 §9.1)
# =============================================================================


class TestMissingData:
    """Tests for missing data handling (returns neutral score 70)."""

    def test_no_current_role_no_history_returns_neutral(self) -> None:
        """No user titles returns neutral score."""
        score = calculate_role_title_score(
            current_role=None,
            work_history_titles=[],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 70.0

    def test_empty_current_role_no_history_returns_neutral(self) -> None:
        """Empty current role with no history returns neutral."""
        score = calculate_role_title_score(
            current_role="",
            work_history_titles=[],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 70.0

    def test_no_job_title_returns_neutral(self) -> None:
        """No job title returns neutral score."""
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=[],
            job_title=None,
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 70.0

    def test_empty_job_title_returns_neutral(self) -> None:
        """Empty job title returns neutral score."""
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=[],
            job_title="",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 70.0

    def test_no_embeddings_no_exact_match_returns_neutral(self) -> None:
        """No embeddings and no exact match returns neutral."""
        score = calculate_role_title_score(
            current_role="Marketing Manager",
            work_history_titles=["Brand Strategist"],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 70.0

    def test_only_user_embedding_missing_returns_neutral(self) -> None:
        """Only user embedding missing returns neutral."""
        score = calculate_role_title_score(
            current_role="Designer",
            work_history_titles=[],
            job_title="Developer",
            user_titles_embedding=None,
            job_title_embedding=[0.5, 0.5],
        )
        assert score == 70.0

    def test_only_job_embedding_missing_returns_neutral(self) -> None:
        """Only job embedding missing returns neutral."""
        score = calculate_role_title_score(
            current_role="Designer",
            work_history_titles=[],
            job_title="Developer",
            user_titles_embedding=[0.5, 0.5],
            job_title_embedding=None,
        )
        assert score == 70.0


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and input validation."""

    def test_empty_work_history_uses_current_role(self) -> None:
        """Empty work history still uses current role for matching."""
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=[],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_none_work_history_treated_as_empty(self) -> None:
        """None work history treated as empty list."""
        score = calculate_role_title_score(
            current_role="Software Engineer",
            work_history_titles=None,  # type: ignore[arg-type]
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_work_history_with_empty_strings_ignored(self) -> None:
        """Empty strings in work history are ignored."""
        score = calculate_role_title_score(
            current_role="Manager",
            work_history_titles=["", "Software Engineer", ""],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_whitespace_only_titles_ignored(self) -> None:
        """Whitespace-only titles are treated as empty."""
        score = calculate_role_title_score(
            current_role="   ",
            work_history_titles=["  ", "Software Engineer"],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_mismatched_embedding_dimensions_raises_error(self) -> None:
        """Mismatched embedding dimensions raise ValueError."""
        with pytest.raises(ValueError, match="dimension|length"):
            calculate_role_title_score(
                current_role="Developer",
                work_history_titles=[],
                job_title="Engineer",
                user_titles_embedding=[0.5, 0.5],
                job_title_embedding=[0.5, 0.5, 0.5],
            )

    def test_empty_embeddings_raises_error(self) -> None:
        """Empty embeddings raise ValueError."""
        with pytest.raises(ValueError, match="empty"):
            calculate_role_title_score(
                current_role="Developer",
                work_history_titles=[],
                job_title="Engineer",
                user_titles_embedding=[],
                job_title_embedding=[],
            )

    def test_oversized_embeddings_raises_error(self) -> None:
        """Oversized embeddings raise ValueError."""
        oversized = [0.1] * 5001
        with pytest.raises(ValueError, match="maximum"):
            calculate_role_title_score(
                current_role="Developer",
                work_history_titles=[],
                job_title="Engineer",
                user_titles_embedding=oversized,
                job_title_embedding=oversized,
            )

    def test_oversized_work_history_raises_error(self) -> None:
        """Oversized work history raises ValueError."""
        oversized_history = [f"Role {i}" for i in range(501)]
        with pytest.raises(ValueError, match="maximum"):
            calculate_role_title_score(
                current_role="Developer",
                work_history_titles=oversized_history,
                job_title="Engineer",
                user_titles_embedding=None,
                job_title_embedding=None,
            )


# =============================================================================
# Worked Examples (from REQ-008 §4.5)
# =============================================================================


class TestWorkedExamples:
    """Worked examples based on REQ-008 spec."""

    def test_example_exact_match(self) -> None:
        """Example 1: Exact match after normalization.

        User: "Senior Software Engineer", "Software Engineer"
        Job: "Software Engineer"
        Expected: 100 (exact match found)
        """
        score = calculate_role_title_score(
            current_role="Senior Software Engineer",
            work_history_titles=["Software Engineer"],
            job_title="Software Engineer",
            user_titles_embedding=None,
            job_title_embedding=None,
        )
        assert score == 100.0

    def test_example_high_semantic_similarity(self) -> None:
        """Example 2: High semantic similarity.

        User: "Backend Developer", "Python Developer"
        Job: "Senior Software Engineer"
        Cosine similarity ~0.7 → Score ~85
        """
        # Simulate embeddings with cosine ~0.7
        user_emb = [1.0, 0.0]
        job_emb = [0.7, 0.714]  # Approx unit vector at arccos(0.7)
        score = calculate_role_title_score(
            current_role="Backend Developer",
            work_history_titles=["Python Developer"],
            job_title="Senior Software Engineer",
            user_titles_embedding=user_emb,
            job_title_embedding=job_emb,
        )
        assert score == pytest.approx(85.0, abs=1.0)

    def test_example_low_semantic_similarity(self) -> None:
        """Example 3: Low semantic similarity (different domains).

        User: "Marketing Manager", "Brand Strategist"
        Job: "Data Scientist"
        Cosine similarity ~-0.2 → Score ~40
        """
        # Simulate embeddings with cosine ~-0.2
        user_emb = [1.0, 0.0]
        job_emb = [-0.2, 0.98]  # Approx unit vector at arccos(-0.2)
        score = calculate_role_title_score(
            current_role="Marketing Manager",
            work_history_titles=["Brand Strategist"],
            job_title="Data Scientist",
            user_titles_embedding=user_emb,
            job_title_embedding=job_emb,
        )
        assert score == pytest.approx(40.0, abs=1.0)
