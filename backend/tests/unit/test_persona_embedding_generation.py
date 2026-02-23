"""Tests for persona embedding generation.

REQ-008 §6.3: Persona Embedding Generation.

Tests the functions that build text from persona data and generate
embeddings for hard_skills, soft_skills, and logistics types.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.services.persona_embedding_generator import (
    build_hard_skills_text,
    build_logistics_text,
    build_soft_skills_text,
    generate_persona_embeddings,
)

# =============================================================================
# Fixtures
# =============================================================================


class MockSkill:
    """Mock Skill object for testing."""

    def __init__(
        self,
        skill_name: str,
        skill_type: str,
        proficiency: str = "Proficient",
    ):
        self.skill_name = skill_name
        self.skill_type = skill_type
        self.proficiency = proficiency


class MockPersona:
    """Mock Persona object for testing."""

    def __init__(
        self,
        persona_id: uuid.UUID | None = None,
        skills: list[MockSkill] | None = None,
        home_city: str = "San Francisco",
        home_state: str = "California",
        home_country: str = "USA",
        remote_preference: str = "Hybrid OK",
        commutable_cities: list[str] | None = None,
        industry_exclusions: list[str] | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = persona_id or uuid.uuid4()
        self.skills = skills or []
        self.home_city = home_city
        self.home_state = home_state
        self.home_country = home_country
        self.remote_preference = remote_preference
        self.commutable_cities = commutable_cities or []
        self.industry_exclusions = industry_exclusions or []
        self.updated_at = updated_at or datetime.now()


@pytest.fixture
def sample_hard_skills() -> list[MockSkill]:
    """Sample hard skills for testing."""
    return [
        MockSkill("Python", "Hard", "Expert"),
        MockSkill("AWS", "Hard", "Proficient"),
        MockSkill("Docker", "Hard", "Familiar"),
    ]


@pytest.fixture
def sample_soft_skills() -> list[MockSkill]:
    """Sample soft skills for testing."""
    return [
        MockSkill("Leadership", "Soft"),
        MockSkill("Communication", "Soft"),
        MockSkill("Problem Solving", "Soft"),
    ]


@pytest.fixture
def sample_persona(
    sample_hard_skills: list[MockSkill],
    sample_soft_skills: list[MockSkill],
) -> MockPersona:
    """Sample persona with skills for testing."""
    return MockPersona(
        skills=sample_hard_skills + sample_soft_skills,
        home_city="San Francisco",
        home_state="California",
        home_country="USA",
        remote_preference="Remote Only",
        commutable_cities=["Oakland", "San Jose"],
        industry_exclusions=["Defense", "Gambling"],
    )


# =============================================================================
# build_hard_skills_text Tests
# =============================================================================


class TestBuildHardSkillsText:
    """Tests for build_hard_skills_text function."""

    def test_formats_skill_with_proficiency(
        self,
        sample_hard_skills: list[MockSkill],
    ) -> None:
        """Hard skills include proficiency level."""
        result = build_hard_skills_text(sample_hard_skills)

        assert "Python (Expert)" in result
        assert "AWS (Proficient)" in result
        assert "Docker (Familiar)" in result

    def test_joins_with_pipe_separator(
        self,
        sample_hard_skills: list[MockSkill],
    ) -> None:
        """Skills are joined with ' | ' separator."""
        result = build_hard_skills_text(sample_hard_skills)

        assert " | " in result
        parts = result.split(" | ")
        assert len(parts) == 3

    def test_empty_skills_returns_empty_string(self) -> None:
        """Empty skill list returns empty string."""
        result = build_hard_skills_text([])

        assert result == ""

    def test_single_skill(self) -> None:
        """Single skill formats correctly without separator."""
        skills = [MockSkill("Python", "Hard", "Expert")]
        result = build_hard_skills_text(skills)

        assert result == "Python (Expert)"
        assert " | " not in result

    def test_filters_out_soft_skills(self) -> None:
        """Only Hard type skills are included."""
        mixed_skills = [
            MockSkill("Python", "Hard", "Expert"),
            MockSkill("Leadership", "Soft", "Proficient"),
            MockSkill("AWS", "Hard", "Familiar"),
        ]
        result = build_hard_skills_text(mixed_skills)

        assert "Python (Expert)" in result
        assert "AWS (Familiar)" in result
        assert "Leadership" not in result


# =============================================================================
# build_soft_skills_text Tests
# =============================================================================


class TestBuildSoftSkillsText:
    """Tests for build_soft_skills_text function."""

    def test_includes_skill_name_only(
        self,
        sample_soft_skills: list[MockSkill],
    ) -> None:
        """Soft skills use name only, no proficiency."""
        result = build_soft_skills_text(sample_soft_skills)

        assert "Leadership" in result
        assert "Communication" in result
        # Proficiency should NOT be in the result for soft skills
        assert "Proficient" not in result

    def test_joins_with_pipe_separator(
        self,
        sample_soft_skills: list[MockSkill],
    ) -> None:
        """Skills are joined with ' | ' separator."""
        result = build_soft_skills_text(sample_soft_skills)

        parts = result.split(" | ")
        assert len(parts) == 3

    def test_empty_skills_returns_empty_string(self) -> None:
        """Empty skill list returns empty string."""
        result = build_soft_skills_text([])

        assert result == ""

    def test_filters_out_hard_skills(self) -> None:
        """Only Soft type skills are included."""
        mixed_skills = [
            MockSkill("Python", "Hard", "Expert"),
            MockSkill("Leadership", "Soft"),
            MockSkill("AWS", "Hard", "Familiar"),
        ]
        result = build_soft_skills_text(mixed_skills)

        assert "Leadership" in result
        assert "Python" not in result
        assert "AWS" not in result


# =============================================================================
# build_logistics_text Tests
# =============================================================================


class TestBuildLogisticsText:
    """Tests for build_logistics_text function."""

    def test_includes_remote_preference(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Logistics text includes remote preference."""
        result = build_logistics_text(sample_persona)

        assert "Remote Only" in result

    def test_includes_location(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Logistics text includes location."""
        result = build_logistics_text(sample_persona)

        assert "San Francisco" in result
        assert "California" in result
        assert "USA" in result

    def test_includes_commutable_cities(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Logistics text includes commutable cities."""
        result = build_logistics_text(sample_persona)

        assert "Oakland" in result
        assert "San Jose" in result

    def test_includes_industry_exclusions(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Logistics text includes industry exclusions."""
        result = build_logistics_text(sample_persona)

        assert "Defense" in result
        assert "Gambling" in result

    def test_handles_empty_commutable_cities(self) -> None:
        """Works when commutable_cities is empty."""
        persona = MockPersona(commutable_cities=[])
        result = build_logistics_text(persona)

        # Should still have other fields
        assert "Remote preference" in result or "remote" in result.lower()

    def test_handles_empty_industry_exclusions(self) -> None:
        """Works when industry_exclusions is empty."""
        persona = MockPersona(industry_exclusions=[])
        result = build_logistics_text(persona)

        # Should still have other fields
        assert "Remote preference" in result or "remote" in result.lower()


# =============================================================================
# generate_persona_embeddings Tests
# =============================================================================


class TestGeneratePersonaEmbeddings:
    """Tests for generate_persona_embeddings function."""

    @pytest.mark.asyncio
    async def test_generates_all_three_embedding_types(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Generates embeddings for hard_skills, soft_skills, and logistics."""
        mock_embed = AsyncMock(
            return_value=[[0.1] * 1536],
        )

        result = await generate_persona_embeddings(sample_persona, mock_embed)

        assert result.hard_skills is not None
        assert result.soft_skills is not None
        assert result.logistics is not None
        assert mock_embed.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_persona_id(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Result includes the persona ID."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_persona_embeddings(sample_persona, mock_embed)

        assert result.persona_id == sample_persona.id

    @pytest.mark.asyncio
    async def test_includes_version_from_updated_at(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Version is set from persona.updated_at for staleness detection."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_persona_embeddings(sample_persona, mock_embed)

        assert result.version == sample_persona.updated_at

    @pytest.mark.asyncio
    async def test_builds_hard_skills_text_correctly(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Hard skills text includes skill names with proficiency."""
        captured_texts: list[str] = []

        async def capture_embed(text: str) -> list[list[float]]:
            captured_texts.append(text)
            return [[0.1] * 1536]

        await generate_persona_embeddings(sample_persona, capture_embed)

        # First call should be hard skills
        hard_skills_text = captured_texts[0]
        assert "Python (Expert)" in hard_skills_text
        assert "AWS (Proficient)" in hard_skills_text

    @pytest.mark.asyncio
    async def test_builds_soft_skills_text_correctly(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Soft skills text includes skill names only."""
        captured_texts: list[str] = []

        async def capture_embed(text: str) -> list[list[float]]:
            captured_texts.append(text)
            return [[0.1] * 1536]

        await generate_persona_embeddings(sample_persona, capture_embed)

        # Second call should be soft skills
        soft_skills_text = captured_texts[1]
        assert "Leadership" in soft_skills_text
        assert "Communication" in soft_skills_text
        # No proficiency in soft skills
        assert "Proficient" not in soft_skills_text

    @pytest.mark.asyncio
    async def test_builds_logistics_text_correctly(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Logistics text includes location preferences."""
        captured_texts: list[str] = []

        async def capture_embed(text: str) -> list[list[float]]:
            captured_texts.append(text)
            return [[0.1] * 1536]

        await generate_persona_embeddings(sample_persona, capture_embed)

        # Third call should be logistics
        logistics_text = captured_texts[2]
        assert "Remote Only" in logistics_text
        assert "San Francisco" in logistics_text

    @pytest.mark.asyncio
    async def test_stores_source_text_in_result(
        self,
        sample_persona: MockPersona,
    ) -> None:
        """Result includes the source text used for embedding."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_persona_embeddings(sample_persona, mock_embed)

        assert "Python" in result.hard_skills.source_text
        assert "Leadership" in result.soft_skills.source_text
        assert "Remote" in result.logistics.source_text

    @pytest.mark.asyncio
    async def test_handles_empty_skills(self) -> None:
        """Works when persona has no skills."""
        persona = MockPersona(skills=[])
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_persona_embeddings(persona, mock_embed)

        # Should still generate embeddings (empty text is valid)
        assert result.hard_skills.source_text == ""
        assert result.soft_skills.source_text == ""
