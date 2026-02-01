"""Tests for embedding freshness check.

REQ-008 §6.6: Embedding Freshness Check.

Tests cover:
- is_embedding_fresh() for persona embeddings
- is_embedding_fresh() for job embeddings
- Staleness detection when source text changes
"""

from app.services.embedding_storage import (
    compute_source_hash,
    is_embedding_fresh,
)

# =============================================================================
# is_embedding_fresh Tests — Basic
# =============================================================================


class TestIsEmbeddingFreshBasic:
    """Basic tests for is_embedding_fresh()."""

    def test_fresh_when_hash_matches(self) -> None:
        """Returns True when current hash matches stored hash."""
        source_text = "Python (5+ years) | SQL | AWS"
        stored_hash = compute_source_hash(source_text)

        result = is_embedding_fresh(
            current_source_text=source_text,
            stored_hash=stored_hash,
        )

        assert result is True

    def test_stale_when_hash_differs(self) -> None:
        """Returns False when current hash differs from stored hash."""
        original_text = "Python (5+ years) | SQL"
        updated_text = "Python (7+ years) | SQL | Kubernetes"
        stored_hash = compute_source_hash(original_text)

        result = is_embedding_fresh(
            current_source_text=updated_text,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_stale_with_empty_stored_hash(self) -> None:
        """Returns False when stored hash is empty (never generated)."""
        source_text = "Python | SQL"

        result = is_embedding_fresh(
            current_source_text=source_text,
            stored_hash="",
        )

        assert result is False


# =============================================================================
# is_embedding_fresh Tests — Edge Cases
# =============================================================================


class TestIsEmbeddingFreshEdgeCases:
    """Edge case tests for is_embedding_fresh()."""

    def test_empty_source_text_can_be_fresh(self) -> None:
        """Empty source text with matching empty hash is fresh."""
        source_text = ""
        stored_hash = compute_source_hash("")

        result = is_embedding_fresh(
            current_source_text=source_text,
            stored_hash=stored_hash,
        )

        assert result is True

    def test_whitespace_changes_cause_staleness(self) -> None:
        """Whitespace differences make embedding stale."""
        original = "Python | SQL"
        modified = "Python  |  SQL"  # Extra spaces
        stored_hash = compute_source_hash(original)

        result = is_embedding_fresh(
            current_source_text=modified,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_case_changes_cause_staleness(self) -> None:
        """Case differences make embedding stale."""
        original = "Python | SQL"
        modified = "python | sql"
        stored_hash = compute_source_hash(original)

        result = is_embedding_fresh(
            current_source_text=modified,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_newline_changes_cause_staleness(self) -> None:
        """Newline differences make embedding stale."""
        original = "Python\nSQL"
        modified = "Python\r\nSQL"
        stored_hash = compute_source_hash(original)

        result = is_embedding_fresh(
            current_source_text=modified,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_unicode_text_freshness(self) -> None:
        """Unicode text is handled correctly."""
        source_text = "Python 🐍 | 日本語"
        stored_hash = compute_source_hash(source_text)

        result = is_embedding_fresh(
            current_source_text=source_text,
            stored_hash=stored_hash,
        )

        assert result is True


# =============================================================================
# Practical Scenarios
# =============================================================================


class TestFreshnessPracticalScenarios:
    """Practical scenarios for embedding freshness."""

    def test_skill_added_makes_stale(self) -> None:
        """Adding a skill to persona makes embedding stale."""
        original = "Python (5+ years) | SQL (3 years)"
        updated = "Python (5+ years) | SQL (3 years) | Docker (2 years)"
        stored_hash = compute_source_hash(original)

        result = is_embedding_fresh(
            current_source_text=updated,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_experience_level_change_makes_stale(self) -> None:
        """Changing experience level makes embedding stale."""
        original = "Python (3+ years)"
        updated = "Python (5+ years)"
        stored_hash = compute_source_hash(original)

        result = is_embedding_fresh(
            current_source_text=updated,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_job_requirements_change_makes_stale(self) -> None:
        """Changing job requirements makes embedding stale."""
        original = "Required: Python, SQL"
        updated = "Required: Python, SQL, Kubernetes"
        stored_hash = compute_source_hash(original)

        result = is_embedding_fresh(
            current_source_text=updated,
            stored_hash=stored_hash,
        )

        assert result is False

    def test_unchanged_text_stays_fresh(self) -> None:
        """Re-computing with same text stays fresh."""
        text = "Senior Software Engineer | Remote OK | 150-180k"
        stored_hash = compute_source_hash(text)

        # Multiple checks with same text
        assert is_embedding_fresh(text, stored_hash) is True
        assert is_embedding_fresh(text, stored_hash) is True
