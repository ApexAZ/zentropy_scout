"""Tests for job embedding generation.

REQ-008 §6.4: Job Embedding Generation.

Tests the functions that build text from job posting data and generate
embeddings for requirements and culture types.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.services.job_embedding_generator import (
    JobEmbeddingData,
    JobEmbeddingsResult,
    build_culture_text,
    build_requirements_text,
    generate_job_embeddings,
    get_neutral_embedding,
)

# =============================================================================
# Fixtures
# =============================================================================


class MockExtractedSkill:
    """Mock ExtractedSkill object for testing.

    Attributes:
        skill_name: Name of the skill.
        skill_type: Type of skill (Hard/Soft).
        is_required: Whether the skill is required.
        years_requested: Years of experience requested.
    """

    def __init__(
        self,
        skill_name: str,
        skill_type: str = "Hard",
        is_required: bool = True,
        years_requested: int | None = None,
    ):
        self.skill_name = skill_name
        self.skill_type = skill_type
        self.is_required = is_required
        self.years_requested = years_requested


class MockJobPosting:
    """Mock JobPosting object for testing.

    Attributes:
        id: UUID of the job posting.
        extracted_skills: List of skills extracted from the job.
        culture_text: LLM-extracted culture/values text.
        years_experience_min: Minimum years experience required.
        years_experience_max: Maximum years experience required.
        updated_at: Timestamp for staleness detection.
    """

    def __init__(
        self,
        job_id: uuid.UUID | None = None,
        extracted_skills: list[MockExtractedSkill] | None = None,
        culture_text: str | None = None,
        years_experience_min: int | None = None,
        years_experience_max: int | None = None,
        updated_at: datetime | None = None,
    ):
        self.id = job_id or uuid.uuid4()
        self.extracted_skills = extracted_skills or []
        self.culture_text = culture_text
        self.years_experience_min = years_experience_min
        self.years_experience_max = years_experience_max
        self.updated_at = updated_at or datetime.now()


@pytest.fixture
def sample_required_skills() -> list[MockExtractedSkill]:
    """Sample required skills for testing."""
    return [
        MockExtractedSkill("Python", "Hard", is_required=True, years_requested=5),
        MockExtractedSkill("SQL", "Hard", is_required=True),
        MockExtractedSkill("Kubernetes", "Hard", is_required=True, years_requested=3),
    ]


@pytest.fixture
def sample_preferred_skills() -> list[MockExtractedSkill]:
    """Sample preferred skills for testing."""
    return [
        MockExtractedSkill("Terraform", "Hard", is_required=False),
        MockExtractedSkill("Go", "Hard", is_required=False),
    ]


@pytest.fixture
def sample_job_posting(
    sample_required_skills: list[MockExtractedSkill],
    sample_preferred_skills: list[MockExtractedSkill],
) -> MockJobPosting:
    """Sample job posting with skills and culture for testing."""
    return MockJobPosting(
        extracted_skills=sample_required_skills + sample_preferred_skills,
        culture_text="We value collaboration, innovation, and work-life balance.",
        years_experience_min=5,
        years_experience_max=8,
    )


# =============================================================================
# build_requirements_text Tests
# =============================================================================


class TestBuildRequirementsText:
    """Tests for build_requirements_text function."""

    def test_includes_required_skills_with_years(
        self,
        sample_required_skills: list[MockExtractedSkill],
    ) -> None:
        """Required skills with years show the years requirement."""
        result = build_requirements_text(sample_required_skills, None, None)

        assert "Python (5+ years)" in result
        assert "Kubernetes (3+ years)" in result

    def test_required_skills_without_years_show_name_only(
        self,
        sample_required_skills: list[MockExtractedSkill],
    ) -> None:
        """Required skills without years just show skill name."""
        result = build_requirements_text(sample_required_skills, None, None)

        # SQL has no years_requested, so it appears without parentheses
        assert "SQL" in result
        # SQL should NOT have parentheses (unlike Python which has years)
        assert "SQL (" not in result

    def test_includes_preferred_skills(
        self,
        sample_required_skills: list[MockExtractedSkill],
        sample_preferred_skills: list[MockExtractedSkill],
    ) -> None:
        """Preferred skills are included in the text."""
        all_skills = sample_required_skills + sample_preferred_skills
        result = build_requirements_text(all_skills, None, None)

        assert "Terraform" in result
        assert "Go" in result

    def test_separates_required_and_preferred(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Required and preferred are labeled separately."""
        result = build_requirements_text(
            sample_job_posting.extracted_skills,
            sample_job_posting.years_experience_min,
            sample_job_posting.years_experience_max,
        )

        assert "Required:" in result
        assert "Preferred:" in result

    def test_includes_experience_range(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Experience range is included in the text."""
        result = build_requirements_text(
            sample_job_posting.extracted_skills,
            sample_job_posting.years_experience_min,
            sample_job_posting.years_experience_max,
        )

        assert "Experience:" in result
        assert "5" in result
        assert "8" in result

    def test_handles_missing_experience_range(self) -> None:
        """Works when experience range is not specified."""
        skills = [MockExtractedSkill("Python", "Hard", is_required=True)]
        result = build_requirements_text(skills, None, None)

        # Should still produce output
        assert "Python" in result
        # Should show "Not specified" for missing experience
        assert "Not specified" in result

    def test_empty_skills_returns_empty_string(self) -> None:
        """Empty skill list returns empty string."""
        result = build_requirements_text([], None, None)

        assert result == ""

    def test_joins_skills_with_pipe_separator(
        self,
        sample_required_skills: list[MockExtractedSkill],
    ) -> None:
        """Skills are joined with ' | ' separator."""
        result = build_requirements_text(sample_required_skills, None, None)

        assert " | " in result

    def test_no_preferred_shows_none(self) -> None:
        """When no preferred skills, shows 'None' for that section."""
        skills = [MockExtractedSkill("Python", "Hard", is_required=True)]
        result = build_requirements_text(skills, 3, 5)

        assert "Preferred: None" in result or "Preferred:" in result


# =============================================================================
# build_culture_text Tests
# =============================================================================


class TestBuildCultureText:
    """Tests for build_culture_text function."""

    def test_returns_culture_text_directly(self) -> None:
        """Culture text is returned as-is."""
        culture = "We value innovation and collaboration."
        result = build_culture_text(culture)

        assert result == culture

    def test_returns_empty_for_none(self) -> None:
        """Returns empty string for None culture text."""
        result = build_culture_text(None)

        assert result == ""

    def test_returns_empty_for_empty_string(self) -> None:
        """Returns empty string for empty culture text."""
        result = build_culture_text("")

        assert result == ""

    def test_returns_empty_for_whitespace_only(self) -> None:
        """Returns empty string for whitespace-only culture text."""
        result = build_culture_text("   ")

        assert result == ""


# =============================================================================
# get_neutral_embedding Tests
# =============================================================================


class TestGetNeutralEmbedding:
    """Tests for get_neutral_embedding function."""

    def test_returns_correct_dimensions(self) -> None:
        """Returns 1536-dimensional vector."""
        result = get_neutral_embedding()

        assert len(result) == 1536

    def test_all_values_are_zero(self) -> None:
        """All values in the vector are 0.0."""
        result = get_neutral_embedding()

        assert all(v == 0.0 for v in result)


# =============================================================================
# JobEmbeddingsResult Tests
# =============================================================================


class TestJobEmbeddingsResult:
    """Tests for JobEmbeddingsResult dataclass."""

    def test_has_required_fields(self) -> None:
        """Result has job_id and both embedding types."""
        job_id = uuid.uuid4()
        version = datetime.now()

        result = JobEmbeddingsResult(
            job_id=job_id,
            requirements=JobEmbeddingData(
                vector=[0.1] * 1536,
                source_text="Python (Expert)",
            ),
            culture=JobEmbeddingData(
                vector=[0.2] * 1536,
                source_text="We value collaboration.",
            ),
            version=version,
            model_name="text-embedding-3-small",
        )

        assert result.job_id == job_id
        assert len(result.requirements.vector) == 1536
        assert len(result.culture.vector) == 1536
        assert result.version == version
        assert result.model_name == "text-embedding-3-small"


# =============================================================================
# generate_job_embeddings Tests
# =============================================================================


class TestGenerateJobEmbeddings:
    """Tests for generate_job_embeddings function."""

    @pytest.mark.asyncio
    async def test_generates_both_embedding_types(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Generates embeddings for requirements and culture."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(sample_job_posting, mock_embed)

        assert result.requirements is not None
        assert result.culture is not None
        # Two calls: requirements and culture
        assert mock_embed.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_job_id(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Result includes the job ID."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(sample_job_posting, mock_embed)

        assert result.job_id == sample_job_posting.id

    @pytest.mark.asyncio
    async def test_includes_version_from_updated_at(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Version is set from job.updated_at for staleness detection."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(sample_job_posting, mock_embed)

        assert result.version == sample_job_posting.updated_at

    @pytest.mark.asyncio
    async def test_builds_requirements_text_correctly(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Requirements text includes skills with years."""
        captured_texts: list[str] = []

        async def capture_embed(text: str) -> list[list[float]]:
            captured_texts.append(text)
            return [[0.1] * 1536]

        await generate_job_embeddings(sample_job_posting, capture_embed)

        # First call should be requirements
        requirements_text = captured_texts[0]
        assert "Python (5+ years)" in requirements_text
        assert "Kubernetes (3+ years)" in requirements_text
        assert "Terraform" in requirements_text

    @pytest.mark.asyncio
    async def test_builds_culture_text_correctly(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Culture text is passed to embedding function."""
        captured_texts: list[str] = []

        async def capture_embed(text: str) -> list[list[float]]:
            captured_texts.append(text)
            return [[0.1] * 1536]

        await generate_job_embeddings(sample_job_posting, capture_embed)

        # Second call should be culture
        culture_text = captured_texts[1]
        assert "collaboration" in culture_text

    @pytest.mark.asyncio
    async def test_stores_source_text_in_result(
        self,
        sample_job_posting: MockJobPosting,
    ) -> None:
        """Result includes the source text used for embedding."""
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(sample_job_posting, mock_embed)

        assert "Python" in result.requirements.source_text
        assert "collaboration" in result.culture.source_text

    @pytest.mark.asyncio
    async def test_handles_empty_skills(self) -> None:
        """Works when job has no extracted skills."""
        job = MockJobPosting(
            extracted_skills=[],
            culture_text="Great team culture.",
        )
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(job, mock_embed)

        # Should still generate embeddings (empty requirements)
        assert result.requirements.source_text == ""
        # Culture should still work
        assert "culture" in result.culture.source_text

    @pytest.mark.asyncio
    async def test_uses_neutral_embedding_for_missing_culture(self) -> None:
        """Uses zero vector for jobs without culture text."""
        job = MockJobPosting(
            extracted_skills=[MockExtractedSkill("Python", "Hard")],
            culture_text=None,
        )
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(job, mock_embed)

        # Culture should be neutral (zero vector)
        assert all(v == 0.0 for v in result.culture.vector)
        assert result.culture.source_text == ""
        # Only requirements should be embedded (1 call)
        assert mock_embed.call_count == 1

    @pytest.mark.asyncio
    async def test_uses_neutral_embedding_for_empty_culture(self) -> None:
        """Uses zero vector for jobs with empty culture text."""
        job = MockJobPosting(
            extracted_skills=[MockExtractedSkill("Python", "Hard")],
            culture_text="   ",  # Whitespace only
        )
        mock_embed = AsyncMock(return_value=[[0.1] * 1536])

        result = await generate_job_embeddings(job, mock_embed)

        # Culture should be neutral (zero vector)
        assert all(v == 0.0 for v in result.culture.vector)
