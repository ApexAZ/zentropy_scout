"""Tests for embedding types definitions.

REQ-008 §6.1: What Gets Embedded.

Zentropy Scout uses five embedding types for job-persona matching:
- Persona: hard_skills, soft_skills, logistics
- Job: requirements, culture
"""

from app.services.embedding_types import (
    EMBEDDING_CONFIGS,
    EmbeddingType,
    get_job_embedding_types,
    get_persona_embedding_types,
)

# =============================================================================
# Helper Function Tests
# =============================================================================


class TestGetPersonaEmbeddingTypes:
    """Tests for get_persona_embedding_types function."""

    def test_returns_persona_types_only(self) -> None:
        """Returns only persona-related embedding types."""
        types = get_persona_embedding_types()

        assert EmbeddingType.PERSONA_HARD_SKILLS in types
        assert EmbeddingType.PERSONA_SOFT_SKILLS in types
        assert EmbeddingType.PERSONA_LOGISTICS in types
        assert EmbeddingType.JOB_REQUIREMENTS not in types
        assert EmbeddingType.JOB_CULTURE not in types


class TestGetJobEmbeddingTypes:
    """Tests for get_job_embedding_types function."""

    def test_returns_job_types_only(self) -> None:
        """Returns only job-related embedding types."""
        types = get_job_embedding_types()

        assert EmbeddingType.JOB_REQUIREMENTS in types
        assert EmbeddingType.JOB_CULTURE in types
        assert EmbeddingType.PERSONA_HARD_SKILLS not in types
        assert EmbeddingType.PERSONA_SOFT_SKILLS not in types
        assert EmbeddingType.PERSONA_LOGISTICS not in types


# =============================================================================
# Embedding Configuration Tests (REQ-008 §6.1)
# =============================================================================


class TestEmbeddingConfigs:
    """Tests for embedding configuration constants."""

    def test_all_types_have_configs(self) -> None:
        """Every embedding type has a configuration entry."""
        for embed_type in EmbeddingType:
            assert embed_type in EMBEDDING_CONFIGS, f"Missing config for {embed_type}"

    def test_config_has_required_fields(self) -> None:
        """Each config has source and description fields."""
        for embed_type, config in EMBEDDING_CONFIGS.items():
            assert "source" in config, f"Missing 'source' for {embed_type}"
            assert "description" in config, f"Missing 'description' for {embed_type}"

    def test_persona_hard_skills_config(self) -> None:
        """Persona hard skills config matches REQ-008 §6.1."""
        config = EMBEDDING_CONFIGS[EmbeddingType.PERSONA_HARD_SKILLS]
        assert "Skill" in config["source"]
        assert "proficiency" in config["description"].lower()

    def test_persona_soft_skills_config(self) -> None:
        """Persona soft skills config matches REQ-008 §6.1."""
        config = EMBEDDING_CONFIGS[EmbeddingType.PERSONA_SOFT_SKILLS]
        assert "Skill" in config["source"]

    def test_persona_logistics_config(self) -> None:
        """Persona logistics config matches REQ-008 §6.1."""
        config = EMBEDDING_CONFIGS[EmbeddingType.PERSONA_LOGISTICS]
        assert "NonNegotiables" in config["source"]

    def test_job_requirements_config(self) -> None:
        """Job requirements config matches REQ-008 §6.1."""
        config = EMBEDDING_CONFIGS[EmbeddingType.JOB_REQUIREMENTS]
        assert "ExtractedSkill" in config["source"]

    def test_job_culture_config(self) -> None:
        """Job culture config matches REQ-008 §6.1 (LLM-extracted)."""
        config = EMBEDDING_CONFIGS[EmbeddingType.JOB_CULTURE]
        # Job culture requires LLM extraction, not structured fields
        assert "LLM" in config["source"] or "extract" in config["source"].lower()
