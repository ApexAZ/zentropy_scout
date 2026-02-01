"""Tests for embedding storage models and repository.

REQ-008 §6.5: Embedding Storage.

Tests cover:
- JobEmbedding model structure
- PersonaEmbedding model structure (verification)
- Embedding type constraints
- Source hash for staleness detection
"""

from app.models.job_posting import JobEmbedding
from app.models.persona_settings import PersonaEmbedding
from app.services.embedding_storage import (
    JobEmbeddingType,
    PersonaEmbeddingType,
    compute_source_hash,
)

# =============================================================================
# Source Hash Tests
# =============================================================================


class TestComputeSourceHash:
    """Tests for compute_source_hash() function."""

    def test_returns_sha256_hex_string(self) -> None:
        """Hash is a 64-character hex string (SHA-256)."""
        result = compute_source_hash("test text")

        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_hash(self) -> None:
        """Same input produces same hash (deterministic)."""
        text = "Python (5+ years) | SQL"
        hash1 = compute_source_hash(text)
        hash2 = compute_source_hash(text)

        assert hash1 == hash2

    def test_different_input_different_hash(self) -> None:
        """Different input produces different hash."""
        hash1 = compute_source_hash("Python (5+ years)")
        hash2 = compute_source_hash("Python (3+ years)")

        assert hash1 != hash2

    def test_empty_string_has_hash(self) -> None:
        """Empty string still produces a valid hash."""
        result = compute_source_hash("")

        assert len(result) == 64

    def test_whitespace_matters(self) -> None:
        """Whitespace differences produce different hashes."""
        hash1 = compute_source_hash("Python | SQL")
        hash2 = compute_source_hash("Python|SQL")

        assert hash1 != hash2


# =============================================================================
# Embedding Type Tests
# =============================================================================


class TestEmbeddingTypes:
    """Tests for embedding type enums."""

    def test_persona_embedding_types(self) -> None:
        """PersonaEmbeddingType has correct values."""
        assert PersonaEmbeddingType.HARD_SKILLS.value == "hard_skills"
        assert PersonaEmbeddingType.SOFT_SKILLS.value == "soft_skills"
        assert PersonaEmbeddingType.LOGISTICS.value == "logistics"

    def test_job_embedding_types(self) -> None:
        """JobEmbeddingType has correct values."""
        assert JobEmbeddingType.REQUIREMENTS.value == "requirements"
        assert JobEmbeddingType.CULTURE.value == "culture"


# =============================================================================
# JobEmbedding Model Tests
# =============================================================================


class TestJobEmbeddingModel:
    """Tests for JobEmbedding ORM model structure."""

    def test_tablename(self) -> None:
        """Table name is job_embeddings."""
        assert JobEmbedding.__tablename__ == "job_embeddings"

    def test_has_required_columns(self) -> None:
        """Model has all required columns."""
        columns = {c.name for c in JobEmbedding.__table__.columns}

        assert "id" in columns
        assert "job_posting_id" in columns
        assert "embedding_type" in columns
        assert "vector" in columns
        assert "model_name" in columns
        assert "model_version" in columns
        assert "source_hash" in columns
        assert "created_at" in columns

    def test_embedding_type_check_constraint(self) -> None:
        """embedding_type has CHECK constraint for valid values."""
        constraints = [c.name for c in JobEmbedding.__table__.constraints]

        # Should have a check constraint for embedding_type
        assert any("jobembedding_type" in (c or "") for c in constraints)


# =============================================================================
# PersonaEmbedding Model Verification Tests
# =============================================================================


class TestPersonaEmbeddingModel:
    """Verification tests for existing PersonaEmbedding model."""

    def test_tablename(self) -> None:
        """Table name is persona_embeddings."""
        assert PersonaEmbedding.__tablename__ == "persona_embeddings"

    def test_has_required_columns(self) -> None:
        """Model has all required columns."""
        columns = {c.name for c in PersonaEmbedding.__table__.columns}

        assert "id" in columns
        assert "persona_id" in columns
        assert "embedding_type" in columns
        assert "vector" in columns
        assert "model_name" in columns
        assert "model_version" in columns
        assert "source_hash" in columns
        assert "created_at" in columns

    def test_embedding_type_check_constraint(self) -> None:
        """embedding_type has CHECK constraint for valid values."""
        constraints = [c.name for c in PersonaEmbedding.__table__.constraints]

        # Should have a check constraint for embedding_type
        assert any("personaembedding_type" in (c or "") for c in constraints)
